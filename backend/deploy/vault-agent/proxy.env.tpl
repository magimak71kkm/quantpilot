{{- with secret "secret/data/quantpilot/core" }}
QP_JWT_SECRET={{ .Data.data.jwt_secret }}
QP_KMS_KEY_B64={{ .Data.data.kms_key_b64 }}
QP_FRONTEND_ORIGIN={{ .Data.data.frontend_origin }}
QP_DATABASE_URL={{ .Data.data.database_url }}
QP_REDIS_URL={{ .Data.data.redis_url }}
{{- end }}
{{- with secret "secret/data/quantpilot/google" }}
QP_GOOGLE_CLIENT_ID={{ .Data.data.client_id }}
QP_GOOGLE_CLIENT_SECRET={{ .Data.data.client_secret }}
QP_GOOGLE_REDIRECT_URI={{ .Data.data.redirect_uri }}
QP_GOOGLE_SCOPES={{ .Data.data.scopes }}
{{- end }}
{{- with secret "secret/data/quantpilot/gemini" }}
QP_GEMINI_API_KEY={{ .Data.data.api_key }}
QP_GEMINI_MODEL={{ .Data.data.model }}
QP_GEMINI_DAILY_QUOTA_PER_USER={{ .Data.data.daily_quota_per_user }}
{{- end }}
