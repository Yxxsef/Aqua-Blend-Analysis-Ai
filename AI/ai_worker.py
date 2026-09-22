import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from env import DB_URL, DB_KEY

from supabase import create_client


POLL_INTERVAL_SECONDS = 2

if not DB_URL or not DB_KEY:
    raise RuntimeError(
        "DB_URL and DB_KEY must be available in the environment."
    )

supabase = create_client(DB_URL, DB_KEY)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def find_next_run():
    response = (
        supabase.table("Runs")
        .select(
            "Id,ExternalId,WorkflowStatus,"
            "MilpOutputId,AiOutputId"
        )
        .eq("WorkflowStatus", "milp_completed")
        .not_.is_("MilpOutputId", "null")
        .is_("AiOutputId", "null")
        .order("Id")
        .limit(1)
        .execute()
    )

    rows = response.data or []

    return rows[0] if rows else None


def claim_run(run_id):
    """
    Conditional claim.

    Only change milp_completed -> ai_running.
    If another worker already claimed it, no row is returned.
    """

    response = (
        supabase.table("Runs")
        .update(
            {
                "WorkflowStatus": "ai_running",
                "AiStartedAt": utc_now(),
                "ProgressMessage":
                    "MILP completed; AI analysis is running.",
                "UpdatedAt": utc_now(),
            }
        )
        .eq("Id", run_id)
        .eq("WorkflowStatus", "milp_completed")
        .is_("AiOutputId", "null")
        .execute()
    )

    rows = response.data or []

    return bool(rows)


def execute_ai(run_id):
    """
    Reuse the existing tested CLI.

    No model config for now:
    deterministic TEMPLATE_FALLBACK is expected and valid.

    --push writes the resulting AI record.
    """

    process = subprocess.run(
        [
            sys.executable,
            "main.py",
            "--run-id",
            str(run_id),
            "--push",
        ],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
    )

    if process.stdout:
        print(process.stdout)

    if process.stderr:
        print(process.stderr, file=sys.stderr)

    if process.returncode != 0:
        raise RuntimeError(
            f"AI pipeline exited with code "
            f"{process.returncode}"
        )


def find_ai_output(run_id):
    response = (
        supabase.table("milp_ai_output")
        .select("id,status,error_code,error_message")
        .eq("origin_run_id", run_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise RuntimeError(
            "AI pipeline completed but no milp_ai_output "
            f"was found for Run {run_id}."
        )

    return rows[0]


def complete_run(run_id, ai_output):
    ai_output_id = ai_output["id"]

    supabase.table("Runs").update(
        {
            "WorkflowStatus": "completed",
            "AiOutputId": ai_output_id,
            "AiCompletedAt": utc_now(),
            "ProgressMessage":
                "MILP optimisation and AI analysis completed.",
            "UpdatedAt": utc_now(),
            "ErrorCode": None,
            "ErrorMessage": None,
        }
    ).eq("Id", run_id).execute()


def fail_ai(run_id, exc):
    supabase.table("Runs").update(
        {
            "WorkflowStatus": "completed_with_ai_error",
            "AiCompletedAt": utc_now(),
            "ProgressMessage":
                "MILP completed, but AI analysis failed.",
            "ErrorCode": "AI_PROCESSING_FAILED",
            "ErrorMessage": str(exc)[:2000],
            "UpdatedAt": utc_now(),
        }
    ).eq("Id", run_id).execute()


def process_run(run):
    run_id = run["Id"]

    if not claim_run(run_id):
        return

    print(
        f"\n[AI WORKER] Processing Run {run_id} "
        f"({run.get('ExternalId')})"
    )

    try:
        execute_ai(run_id)

        ai_output = find_ai_output(run_id)

        complete_run(
            run_id,
            ai_output,
        )

        print(
            f"[AI WORKER] Run {run_id} completed. "
            f"AI output: {ai_output['id']}"
        )

    except Exception as exc:
        print(
            f"[AI WORKER] Run {run_id} failed: {exc}",
            file=sys.stderr,
        )

        fail_ai(
            run_id,
            exc,
        )


def main():
    print(
        "[AI WORKER] AquaBlend AI worker started."
    )

    while True:
        try:
            run = find_next_run()

            if run is None:
                time.sleep(
                    POLL_INTERVAL_SECONDS
                )
                continue

            process_run(run)

        except KeyboardInterrupt:
            print(
                "\n[AI WORKER] Stopped."
            )
            break

        except Exception as exc:
            print(
                f"[AI WORKER] Worker loop error: {exc}",
                file=sys.stderr,
            )

            time.sleep(
                POLL_INTERVAL_SECONDS
            )


if __name__ == "__main__":
    main()