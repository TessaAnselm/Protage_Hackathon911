# RocketRide Integration Setup

RocketRide was one of seven sponsor tools integrated into ProtageOps. For the hackathon, we were given access to a pre-release RocketRide staging environment, so the integration path differed from the publicly documented RocketRide Cloud setup.

The hackathon credentials were scoped to RocketRide's staging environment rather than the public cloud endpoint. Because this staging configuration was not yet part of the public documentation, we needed to determine the correct endpoint and authentication pattern directly from the platform.

To do that, we created a test pipeline in RocketRide's Pipeline Builder, added a Webhook source, and inspected the generated Endpoint Configuration. This exposed the staging endpoint, authorization values, and request format needed to connect ProtageOps successfully.

This document captures that discovery and integration process, including how we verified the configuration and reproduced the working pipeline in the application.

**Reading the screenshots below:** a solid red box hides a sensitive value
(URL path, key, or token) that was blacked out before these were committed —
a red outline highlights the button or tab to notice for that step.

## 1. Add a pipeline

In the Pipeline Builder, open **Pipelines → New pipeline**.

<p align="center">
  <img src="images/rocketride/01-new-pipeline.png" alt="Pipelines tab in the RocketRide Pipeline Builder sidebar" width="500">
</p>

## 2. Add a Webhook setting

A new pipeline asks for a starting source. Pick **Webhook** — this is what
exposes a real HTTP endpoint (with its own URL and auth key) instead of a
purely internal trigger, which is what's needed to find out how RocketRide
expects external callers to authenticate.

<p align="center">
  <img src="images/rocketride/02-select-webhook-source.png" alt="Selecting Webhook as the pipeline's starting source" width="600">
</p>

## 3. Run it in dev

Switch to the **Development** tab and hit **Run**. RocketRide will prompt to
save unsaved pipeline changes before it'll actually start the run — confirm
with **Save & Run**.

<p align="center">
  <img src="images/rocketride/03-run-dev.png" alt="Running the pipeline from the Development tab" width="700">
</p>
<p align="center">
  <img src="images/rocketride/04-save-and-run-dialog.png" alt="Confirming Save &amp; Run on the unsaved-changes prompt" width="420">
</p>

## 4. Back in Design → grab the URL and token

Back on the **Design** tab, click **Endpoint Info** on the Webhook node.

<p align="center">
  <img src="images/rocketride/05-endpoint-info-button.png" alt="Opening Endpoint Info from the Webhook node" width="420">
</p>

This opens **Endpoint Configuration**, which is where the real integration
details live: the webhook interface URL, a URL-with-auth-query variant, a
public authorization key, and a private token — plus a ready-made `curl`
example showing exactly how to call it. This page is the answer to "what
host and auth scheme does RocketRide actually expect," which isn't written
down anywhere else.

<p align="center">
  <img src="images/rocketride/06-endpoint-configuration.png" alt="Endpoint Configuration panel with URL, key, and token fields (sensitive values redacted)" width="600">
</p>

## 5. Download the pipeline folder

From the pipeline list, use the **⋯ → Export** menu to download the pipeline
definition as a `.pipe` file.

<p align="center">
  <img src="images/rocketride/07-export-pipeline.png" alt="Exporting the pipeline as a .pipe file" width="420">
</p>

## 6. Add it to the project folder

The exported file is checked into the repo root as
[`protageopsrun.pipe`](protageopsrun.pipe) — a record of the exact pipeline
shape RocketRide expects (a `chat` source feeding an `llm_openai` component
feeding a `response` output). The backend doesn't load this file at
request time; instead `backend/adapters/rocketride_adapter.py`'s
`_build_pipeline()` rebuilds the equivalent structure in Python and starts it
per-request via the `rocketride` SDK (`RocketRideClient.use(pipeline=...)`),
authenticating with the URL/key pattern discovered in step 4 through the
`ROCKETRIDE_URL` and `ROCKETRIDE_API_KEY` environment variables. Keeping the
exported `.pipe` around is what makes that Python pipeline dict verifiable
against a real, working pipeline instead of a guess.

The **Monitor** tab confirms the whole loop actually works end-to-end once
the app is running and calling it — connections and completed tasks showing
up live for the pipeline the backend calls:

<p align="center">
  <img src="images/rocketride/08-live-monitor.png" alt="Monitor tab showing a live connection and completed tasks against the pipeline" width="700">
</p>

## Result

`backend/adapters/rocketride_adapter.py` uses this exact URL/auth pattern in
production — see the [Sponsor tool integration status](README.md#sponsor-tool-integration-status)
table for how `/api/ask` ("Ask about this migration") uses it at runtime.
