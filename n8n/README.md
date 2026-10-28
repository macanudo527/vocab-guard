# n8n workflow

`workflow.json` is an n8n workflow that writes a Japanese article at a JLPT
level and makes sure every word and kanji in it is on that level's list.

1. A chat model writes a draft from a topic, a level, a target length and an
   article type.
2. The vocab-guard checker splits the text into words and checks each word and
   kanji against the level's lists.
3. Only the failing sentences go back to the model, each with the words to
   replace and the sentences around it. This repeats up to 5 times.
4. The article is saved as a WordPress **draft**, never published, and you get
   a report: first-draft and final pass rates, problems left, rounds used,
   words and kanji caught, every repair, and an estimated cost.

It runs from an n8n form (one article at a time) or from a webhook that takes
the same fields as JSON and answers with the report (for scripts and batch
runs). It uses only built-in n8n nodes and plain JavaScript, so it also runs on
n8n Cloud as long as the checker is reachable from there. Tested on n8n 2.44.6.

## Setup

1. **Run the checker.** With the repo's Docker Compose (`docker compose up`)
   it's already running at `http://checker:8000`. On its own:

   ```sh
   docker run -p 8000:8000 ghcr.io/macanudo527/vocab-guard-checker:0.1
   ```

2. **Import the workflow.** In n8n, create a workflow, open the **...** menu,
   choose **Import from File**, and pick `workflow.json`.
3. **Add the credentials** listed below. Open **Chat model** and **Create
   draft** and choose them.
4. **Check Config.** Set `checker_url` to where n8n can reach the checker. The
   defaults fit the Compose setup.
5. **Publish** the workflow. Then open the form URL shown in **Article form**,
   or post to the **Batch webhook** URL:

   ```sh
   curl -X POST http://localhost:5678/webhook/vocab-guard-batch \
     -H 'content-type: application/json' \
     -d '{"topic": "A day at the zoo", "level": "N4", "target_length": 400, "article_type": "Blog post"}'
   ```

   `level` and `topic` are required. `target_length` (Japanese characters)
   defaults to 400 and `article_type` to "Blog post". A run takes a minute or
   more, so give the client a long timeout.

## Credentials

| Credential | Used by | What to enter |
| --- | --- | --- |
| OpenAI | **Chat model** | An API key from platform.openai.com. |
| WordPress | **Create draft** | A user that can write posts, an [application password](https://make.wordpress.org/core/2020/11/05/application-passwords-integration-guide/) for it (wp-admin > Users > Profile), and the site URL. With the Compose demo, the URL is `http://wordpress` and the `wordpress-setup` container prints an application password into its logs (`docker compose logs wordpress-setup`). |
| Header Auth (optional) | **Check** | Only if the checker runs with `CHECKER_API_KEY`. In **Check**, set Authentication to Generic credential type > Header Auth, with the name `X-API-Key` and the key as the value. |

WordPress only accepts application passwords over HTTPS, unless the site is
set to a local environment as the Compose demo is.

## Settings

Everything you are likely to change is in the **Config** node:

| Field | Default | Meaning |
| --- | --- | --- |
| `checker_url` | `http://checker:8000` | Where n8n reaches the checker. |
| `list` | `jlpt` | Base name of the word list. The level is added, so N4 checks against `jlpt-n4`. |
| `max_rounds` | `5` | Repair rounds before giving up. |
| `draft_model` | `gpt-6.1-sol` | Writes the first draft. |
| `repair_model` | `gpt-6-luna` | Rewrites failing sentences. A smaller, cheaper model is enough. |
| `service_tier` | `flex` | OpenAI's [Flex processing](https://developers.openai.com/api/docs/guides/flex-processing): Batch prices for slower answers. Use `default` for full speed at full price. **Chat model** sends it in the request body (Options > Extra Body); remove it there if you point the node at a non-OpenAI endpoint that rejects unknown fields. |
| `*_price_input`, `*_price_output` | Flex prices | USD per 1M tokens, for the cost estimate. Update them when you change models or tier. |

The prompts are plain text in **Draft prompt** and **Repair prompt**. The
model's answers are read as JSON by **Read draft** and **Apply repairs**.

Flex calls can be turned away when OpenAI is busy (HTTP 429). The model node
retries 4 times and both LLM steps retry the whole call up to 5 times, so a
busy period makes a run slower instead of failing it.

## Swapping word lists

The checker serves every list in its lists folder. To add your own, make a
directory in the format described in [lists/README.md](../lists/README.md)
(`meta.json`, `vocab.csv`, and `kanji.csv` for kanji levels), and mount it
under `/app/lists/data/` in the checker container:

```sh
docker run -p 8000:8000 -v "$PWD/my-list:/app/lists/data/my-list:ro" \
  ghcr.io/macanudo527/vocab-guard-checker:0.1
```

Then set `list` in **Config** to the list's `name`. If its levels aren't
N5–N1, change the **Level** options in **Article form** and the wording in the
two prompt nodes, which say "JLPT". `GET /lists` on the checker shows the list
names it has loaded.

## Swapping the LLM provider

The prompts are plain text and ask for plain JSON, with no provider-specific
features, so any chat model node works:

1. Add the provider's chat model node (for example Anthropic Chat Model or
   Google Gemini Chat Model) and its credential.
2. Connect it to both **Write draft** and **Repair sentences**, and delete
   **Chat model**.
3. Set the new node's model to the expression `{{ $json.model }}`.
4. Change `draft_model`, `repair_model` and the prices in **Config**.
   `service_tier` is OpenAI-only; other providers ignore it.

## Limits

- **Japanese only.** The checker accepts `lang: "ja"` for now.
- **Words and kanji, not grammar.** A sentence can use only N5 words and still
  use grammar above N5.
- **Text written mostly in kana is harder to split into words.** When a repair
  writes several words in hiragana in a row, the analyzer sometimes splits them
  wrongly. For example, `ちかくで` can be read as `ちかい` plus the
  conjunction `で`, which then fails as an unknown word. The loop spends
  rounds on these, and they can show up in the problems left.
- **Names are allowed.** Words the analyzer tags as proper nouns (people,
  places, organizations) pass by default.
- **Some articles still fail.** After `max_rounds` the article is saved as a
  draft anyway, and the report lists what's left for a person to fix.
- **Costs are estimates.** n8n doesn't pass a chat model's real token counts
  to later nodes, so the report estimates them from text length. Hidden
  reasoning tokens aren't included, so the real cost is higher: in one test
  run gpt-6.1-sol used 917 output tokens for a draft estimated at 302, and the
  article cost 2.7 times the estimate. Exact counts are in each execution's
  log in n8n.
- **The form waits for the whole run.** It shows a waiting page until the
  draft is saved, usually a minute or two, longer when Flex is busy.
- **The webhook has no authentication.** Production webhook URLs are public.
  If n8n is reachable from the internet, add Header Auth to **Batch webhook**.
- **One article per webhook call.** To run many, call the webhook once per
  article. `scripts/benchmark.py` does this for the results in
  [docs/RESULTS.md](../docs/RESULTS.md).
- **Up to 20,000 characters** per check by default (the checker's
  `MAX_TEXT_CHARS`).
