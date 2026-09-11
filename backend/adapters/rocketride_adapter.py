"""
RocketRide sponsor adapter — orchestrates a hosted AI pipeline for
migration Q&A.

Real, end-to-end: ROCKETRIDE_API_KEY authenticates against RocketRide's
staging endpoint (https://staging.rocketride.ai/ — their default
https://cloud.rocketride.ai/ rejects this key). Each call to ask()
defines a small pipeline (chat source -> llm_openai -> response, per
RocketRide's documented pipeline schema), starts it with
client.use(pipeline=...), and asks the question with client.chat(). The
pipeline actually runs on RocketRide's infrastructure — this isn't a
thin wrapper around a direct OpenAI call, it's OpenAI called *by* the
RocketRide-hosted node.

A separate `prompt` component (tried first) turned out to drop the
forwarded question — its output to the LLM didn't reliably carry the
original question text alongside the static prompt, so context is
inlined directly into the question sent via Question.addQuestion()
instead of relying on that node.
"""
import os
import uuid

from rocketride import Question, RocketRideClient

ROCKETRIDE_URI = "https://staging.rocketride.ai/"
LIVE = True


def _build_pipeline() -> dict:
    return {
        "project_id": str(uuid.uuid4()),
        "source": "source_1",
        "components": [
            {"id": "source_1", "provider": "chat", "config": {}},
            {
                "id": "llm_1",
                "provider": "llm_openai",
                "config": {
                    "profile": "openai-4o-mini",
                    "openai-4o-mini": {"apikey": os.environ["LLM_API_KEY"]},
                },
                "input": [{"from": "source_1", "lane": "questions"}],
            },
            {
                "id": "target_1",
                "provider": "response",
                "config": {},
                "input": [{"from": "llm_1", "lane": "answers"}],
            },
        ],
    }


async def ask(question: str, context: str) -> str:
    client = RocketRideClient(
        uri=os.environ.get("ROCKETRIDE_URL", ROCKETRIDE_URI),
        auth=os.environ["ROCKETRIDE_API_KEY"],
    )
    await client.connect()
    try:
        result = await client.use(pipeline=_build_pipeline())
        token = result["token"]
        try:
            q = Question()
            q.addQuestion(f"{context}\n\nQuestion: {question}")
            response = await client.chat(token=token, question=q)
        finally:
            await client.terminate(token)
        answers = response.get("answers") or []
        return answers[0] if answers else "(RocketRide returned no answer)"
    finally:
        await client.disconnect()
