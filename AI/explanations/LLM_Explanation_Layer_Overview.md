# AquaBlend LLM Explanation Layer Overview



## 1. Purpose



The AquaBlend explanation layer converts structured optimisation results into a readable report while keeping the MILP output as the factual source of truth.



The LLM is not used to make optimisation decisions. Its role is limited to improving the readability of an already generated deterministic report. If the LLM is unavailable, produces an invalid response, or fails factual and safety validation, AquaBlend keeps the deterministic report as the safe fallback.



The main components covered by this document are:



- `json_explainer.py`

- `prompts.py`

- `model_runner.py`

- `llm_validator.py`



Together, these components provide deterministic report generation, controlled LLM rewriting, validation, and fallback behaviour.



---



## 2. End-to-End Explanation Flow



The explanation flow can be summarised as follows:



```text

Adapted MILP Results

        |

        v

json_explainer.py

        |

        v

Deterministic Report

        |

        v

prompts.py

        |

        v

model_runner.py

        |

        +--------------------------+

        |                          |

        | model/runtime failure    | successful rewrite

        v                          v

TEMPLATE_FALLBACK          LLM_UNVALIDATED

                                   |

                                   v

                           llm_validator.py

                              /         \\

                           PASS           FAIL

                            |              |

                            v              v

                     LLM_VALIDATED   TEMPLATE_FALLBACK

```



The deterministic report remains the trusted baseline throughout this process. The LLM rewrite is not trusted merely because the model call succeeds.



---



## 3. `json_explainer.py` — Deterministic Explanation Generator



`json_explainer.py` generates the deterministic AquaBlend report without making any LLM call.



It consumes the stable internal results shape produced upstream by the results adapter. The top-level fields use the adapted naming convention, while nested fields remain aligned with the Results JSON contract.



The two required fields are:



- `status`

- `scenarioId`



If either is missing, report generation stops with `ExplainerInputError`.



Other report fields are treated as optional. Missing optional information is reported or omitted according to the reporting rules rather than being invented.



For an `OPTIMAL` result, the generator can report:



1. Scenario and solver status

2. Result availability

3. Demand-zone results

4. Selected sources and blend ratios

5. Unused sources

6. Active plants and transfer results

7. Cost summary

8. Plant-inflow water quality

9. Binding constraints

10. Data flags and estimated values

11. Alternatives and sensitivity

12. Prototype disclaimer



Currently, only `OPTIMAL` is included in `FULL_REPORT_STATUSES`. Other solver states receive a restricted status-focused report rather than a full recommendation-style report.



The deterministic generator follows a conservative rule: it reports available facts and does not invent missing values, source-selection reasons, recommendations, calculations, or drinking-water safety claims.



The main orchestration function is:



`generate_explanation(data)`



This validates the input and assembles the report sections in the required order.



---



## 4. `prompts.py` — Controlled Rewrite Prompt



`prompts.py` defines the instructions supplied to the LLM.



The current prompt version is:



`aquablend-report-rewrite-v1.2`



The prompt states that the deterministic report is the complete factual source and that the MILP optimiser remains the decision-maker.



The LLM may improve readability and sentence flow, but it must preserve factual information including:



- numbers and decimal values

- percentages

- units

- identifiers

- source, plant and scenario names

- solver and quality statuses

- warnings

- limitations

- estimated-value disclosures

- disclaimers



The prompt prevents the model from adding calculations, estimates, causal explanations, recommendations, regulatory claims, compliance claims, operational advice, or drinking-water safety claims.



The deterministic report is placed inside:



`<deterministic_report> ... </deterministic_report>`



These tags delimit report data from instructions. The prompt explicitly tells the model that these tags are not part of the report and must not appear in the generated response.



If the model cannot perform a faithful rewrite, it is instructed to return:



`[REWRITE_FAILED]`



This sentinel allows `model_runner.py` to reject the rewrite and use the deterministic fallback.



---



## 5. `model_runner.py` — LLM Execution and Runtime Fallback



`model_runner.py` sends the controlled prompt to an OpenAI-compatible chat endpoint.



Runtime behaviour is controlled through `ModelConfig`, including:



- model ID

- endpoint/base URL

- API key

- temperature

- top-p

- maximum tokens

- timeout

- seed

- optional frequency penalty



A successful model call does not mean the report is approved.



Successful model output is returned with:



`report_mode = "LLM_UNVALIDATED"`



The candidate must still pass `llm_validator.py` before it can be treated as validated output.



If the model call cannot produce a usable candidate, the original deterministic report is returned with:



`report_mode = "TEMPLATE_FALLBACK"`



Examples of runtime fallback conditions include:



- timeout

- model endpoint unavailable

- malformed or invalid model response

- general model/runtime error

- empty output

- `[REWRITE_FAILED]` returned by the model



The fallback result also records metadata such as the model ID, prompt version, runtime, failure type, and failure message.



---



## 6. `llm_validator.py` — Factual and Safety Validation



`llm_validator.py` compares two plain-text inputs:



1. the trusted deterministic report

2. the candidate LLM rewrite



It does not call the model runner or deterministic generator itself.



The main function is:



`validate_llm_output(deterministic_report, llm_output)`



The validator returns a structured `ValidationResult` containing:



- `critical_result`

- `critical_failures`

- `warnings`



Critical checks include detection of:



- missing or changed numbers

- invented numbers

- incorrect number associations

- missing units or codes

- missing identifiers

- missing or invented status values

- invented reasons, recommendations or claims

- unsafe safety claims

- missing prototype disclaimer

- missing plant-inflow water-quality disclosure

- empty output

- incomplete/truncated output



A single critical failure causes the validation result to be `FAIL`.



Warnings do not independently cause failure. They identify issues worth human review, such as possible new identifiers, weak invented-content phrases, or unusual shortening of the report.



The validator uses deterministic text checks rather than semantic judgement. Therefore, it is designed as an explainable safety and factuality gate, not as a complete semantic verification system.



---



## 7. Report Modes



### `LLM_UNVALIDATED`



This status means the model call succeeded and produced candidate text, but the text has not yet passed factual and safety validation.



It must not be treated as validated report content.



### `LLM_VALIDATED`



This status is appropriate only when an `LLM_UNVALIDATED` candidate passes the critical checks performed by `llm_validator.py`.



The validator itself returns PASS/FAIL and does not directly change the report mode. The caller or pipeline orchestrator is responsible for promoting a successful candidate to `LLM_VALIDATED`.



### `TEMPLATE_FALLBACK`



This status means the deterministic report is being used instead of the LLM rewrite.



Fallback can occur at two main stages:



1. **Model/runtime stage** — for example timeout, unavailable endpoint, invalid response, empty response, model error, or `[REWRITE_FAILED]`.

2. **Validation stage** — when the candidate rewrite fails one or more critical factual or safety checks.



This design ensures that an unsuccessful or unsafe LLM rewrite does not replace the deterministic report.



---



## 8. Why the Deterministic Report Is Important



The deterministic report is more than an alternative presentation mode. It is the trusted baseline used by the LLM pipeline.



It provides:



- the factual content that the LLM is allowed to rewrite

- a usable report when the LLM is unavailable

- the reference text used by `llm_validator.py`

- protection against unsupported LLM additions or omissions



This means AquaBlend can still produce explanation text even when the LLM layer fails.



---



## 9. Known Open Gaps



### 9.1 Repetition-loop



Live model testing identified a case where an LLM entered a long repetition loop near the end of the response, particularly around the Prototype Disclaimer.



`model_runner.py` supports an optional `frequency_penalty` as a possible mitigation. However, this setting is model-dependent and is not guaranteed to work for every OpenAI-compatible model/runtime.



The prompt also tells the model to stop immediately after rewriting the Prototype Disclaimer.



This remains a known gap because model-level repetition cannot be assumed to be completely prevented by prompting or frequency-penalty configuration alone.



### 9.2 Prompt-tag-leak



The deterministic report is wrapped in `<deterministic_report>` and `</deterministic_report>` tags when sent to the model.



These tags are control delimiters and must not appear in the final displayed report. The current prompt explicitly instructs the model never to output these or other XML-like tags.



However, prompt instructions alone cannot guarantee that every model will always obey this requirement. Prompt-tag leakage therefore remains a known gap that should continue to be checked during testing and validation work.



---



## 10. Component Responsibilities



| Component | Responsibility | Trusted output? |

|---|---|---|

| `json_explainer.py` | Generate deterministic report from adapted results | Yes, deterministic baseline |

| `prompts.py` | Build controlled instructions and messages for the LLM | N/A |

| `model_runner.py` | Execute LLM rewrite and handle runtime fallback | LLM output remains unvalidated |

| `llm_validator.py` | Compare candidate rewrite with deterministic report and return PASS/FAIL/warnings | Validation gate |



The separation of these responsibilities keeps deterministic generation, LLM execution and validation independent and easier to test.



---



## 11. Example Decision Flow



A normal successful path is:



```text

Deterministic report generated

        ->

LLM rewrite requested

        ->

Model returns candidate

        ->

Candidate marked LLM_UNVALIDATED

        ->

Validator returns PASS

        ->

Pipeline may use LLM_VALIDATED

```



A model failure path is:



```text

Deterministic report generated

        ->

LLM request fails or returns unusable output

        ->

Original deterministic report returned

        ->

TEMPLATE_FALLBACK

```



A validation failure path is:



```text

Deterministic report generated

        ->

LLM returns candidate

        ->

Candidate marked LLM_UNVALIDATED

        ->

Validator detects critical failure

        ->

Candidate rejected

        ->

Deterministic report retained as TEMPLATE_FALLBACK

```



---



## 12. Summary



The AquaBlend explanation layer uses a deterministic-first architecture.



`json_explainer.py` creates the factual report, `prompts.py` constrains the optional LLM rewrite, `model_runner.py` executes the model and provides runtime fallback, and `llm_validator.py` checks the candidate for factual and safety problems.



An LLM response is never considered trusted merely because generation succeeds. It begins as `LLM_UNVALIDATED` and should become `LLM_VALIDATED` only after passing validation. Otherwise, AquaBlend uses `TEMPLATE_FALLBACK`.



This design keeps the MILP results and deterministic explanation as the source of truth while allowing the LLM to improve readability when it can do so without changing the underlying facts.
