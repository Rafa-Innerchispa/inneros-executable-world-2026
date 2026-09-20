// edge-functions/api/witness.js

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

export function onRequestGet() {
  return json({
    ok: true,
    witness: "inneros-executable-world",
    provider: "Tencent EdgeOne",
    runtime: "edge-function",
    timestamp: new Date().toISOString(),
  });
}

export async function onRequestPost({ request }) {
  let body;

  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }

  const forbidden = ["password", "secret", "token", "api_key"];
  for (const key of forbidden) {
    if (key in body) {
      return json(
        { ok: false, error: `forbidden_field:${key}` },
        400
      );
    }
  }

  const receipt = body.receipt || body;

  return json({
    witnessed: true,
    provider: "Tencent EdgeOne",
    received_at: new Date().toISOString(),
    event_type: body.event_type || receipt.event_type || null,
    session_id: receipt.session_id || null,
    permit_id: receipt.permit_id || null,
    evidence_sha256:
      receipt.evidence_sha256 ||
      receipt.evidence_hash ||
      null,
  });
}
