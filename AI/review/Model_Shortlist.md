# AquaBlend Small LLM Shortlist

**Task:** 24, first LLM prompt and model runner  
**Research date:** 6 August 2026  
**Decision status:** Provisional, pending Task 25 factual and safety evaluation

## Selection requirements

The model must be small enough for local testing, instruction-tuned, licenced for project use, supported by a practical local runtime, and able to rewrite a deterministic report without adding facts. Factual faithfulness is more important than writing style.

## Shortlist

| Model | Developer | Size | Context | Licence and access | Local runtime support | Main fit for AquaBlend | Main concern |
|---|---|---:|---:|---|---|---|---|
| `Qwen/Qwen3-4B-Instruct-2507` | Qwen | 4.0B | 262,144 tokens | Apache 2.0; public model page | Transformers, vLLM, SGLang, Docker Model Runner; official page links quantisations for llama.cpp, Ollama and LM Studio | Strong instruction-following focus; non-thinking output; permissive licence; simple text-only rewrite target | Official page does not state a universal consumer-GPU minimum; local quantised performance must be measured |
| `microsoft/Phi-4-mini-instruct` | Microsoft | 3.8B | 128K tokens | MIT; intended for broad multilingual commercial and research use | Transformers, vLLM, SGLang, Docker Model Runner; quantised local variants are linked | Small, permissive licence, designed for constrained and latency-sensitive environments | Microsoft notes size-related factual limitations; official full-precision testing lists high-end GPUs, so consumer testing should use quantisation |
| `google/gemma-3-4b-it` | Google DeepMind | 4B | 128K input, 8K output | Gemma licence; Hugging Face access requires accepting Google usage terms | Transformers, vLLM, SGLang, Docker Model Runner; quantisations are linked | Small instruction model with strong summarisation and rewriting use cases | Custom licence and gated acceptance create more onboarding friction; multimodal features are unnecessary for this task |

## Provisional choice

### `Qwen/Qwen3-4B-Instruct-2507`

This is the first model to connect.

Reasons:

1. The 4B size is realistic for an 8 GB laptop GPU when a suitable quantised build is used, subject to a real memory and speed test.
2. Apache 2.0 is simpler for team use than a custom usage licence.
3. The model is explicitly non-thinking, which reduces the chance of reasoning blocks appearing in the report output.
4. The model card emphasises improved instruction following and writing quality, which matches a controlled rewrite task.
5. The runner remains model-independent, so Phi-4-mini-instruct or Gemma 3 4B can be tested later without changing the pipeline.

## Generation settings for the first test

- temperature: `0.0`
- top_p: `1.0`
- seed: `0` where supported
- maximum output: `1200` tokens
- timeout: `30` seconds
- input: deterministic fallback report only
- output status before validation: `LLM_UNVALIDATED`

These settings reduce variation but do not guarantee identical output across runtimes or quantisations.

## Acceptance boundary

The provisional model is not recommended for display merely because it runs. Task 25 must reject any output that changes or omits facts, numbers, units, warnings, constraints, source names, water-quality wording, estimate disclosures, or the prototype disclaimer.

The project should remain template-only if no tested model passes the critical factual and safety checks.

## Official sources

- Qwen official model card: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Microsoft official model card: https://huggingface.co/microsoft/Phi-4-mini-instruct
- Google official model card: https://huggingface.co/google/gemma-3-4b-it
- Ollama OpenAI compatibility: https://docs.ollama.com/api/openai-compatibility
- Ollama deterministic setting guidance: https://docs.ollama.com/capabilities/structured-outputs
