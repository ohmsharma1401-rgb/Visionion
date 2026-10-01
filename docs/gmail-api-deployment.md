# Gmail API verification email on Render

Implementation prepared locally on 2026-10-01; not configured or deployed yet.
The current cloud health endpoint reports email delivery unconfigured.

The app uses its existing accounts and six-digit verification codes. Gmail API
replaces only the email transport, using HTTPS rather than SMTP. Verification
and the failed-delivery rollback behavior remain enforced. No additional Python
dependencies are needed: httpx is already in backend requirements.

## Google configuration

1. Complete Google Cloud account setup. Accepting terms requires the owner's
   action or explicit approval. The currently open Cloud console is signed in
   as a different Google account from the intended sender; do not accidentally
   authorize that account as the sender.
2. Select/create a project and enable Gmail API. Configure OAuth branding and
   consent. Use only `https://www.googleapis.com/auth/gmail.send`; mailbox reading
   and deletion scopes are unnecessary.
3. Create an OAuth client and obtain offline user authorization from
   `241240131056.cse@gmail.com`. Credential creation and granting Gmail access need
   explicit approval. Keep the client secret and refresh token private.
4. For an External OAuth app in Testing mode, Gmail-scoped refresh tokens can
   expire after seven days. This is not a stable unattended configuration.
   Follow Google's publishing/verification requirements for the chosen app
   audience before claiming email delivery will remain authorized indefinitely.
5. Configure the backend Render environment:

   - `EMAIL_PROVIDER=gmail_api`
   - `GMAIL_SENDER=241240131056.cse@gmail.com`
   - `GMAIL_CLIENT_ID`: OAuth client ID
   - `GMAIL_CLIENT_SECRET`: OAuth client secret
   - `GMAIL_REFRESH_TOKEN`: authorized sender refresh token

   The sender must be the authorized mailbox or an allowed send-as identity.
   Never place credentials in VITE variables, source control, screenshots or chat.

## Implementation and validation

`backend/email_delivery.py` refreshes access tokens through Google's HTTPS
endpoint, caches them until near expiry, creates MIME/base64url messages and
sends through `/gmail/v1/users/me/messages/send`. Missing configuration and
provider failures return an end-user availability message; provider response
bodies and tokens are not exposed. Gmail failures do not fall back to SMTP.
Render SMTP settings cannot make the health endpoint claim email readiness.

Unit tests use mocked HTTPS requests and send no real email. Four tests passed:
refresh/MIME/cached-token delivery, failed authorization without sending or
secret leakage, incomplete Gmail configuration, and Render SMTP readiness.
The earlier full API test suite remains limited by Windows Application Control
rejecting the installed SQLAlchemy native extension. Compilation and isolated
transport tests passed; actual email delivery and registration are unverified.

Before deployment, resolve full API validation, authorize the sender, and deploy
only the intended email changes (other local storage and documentation work is
also present). After deployment, check health configuration and explicitly
authorize a test email to the owner's mailbox. Then verify successful code
delivery, new-account registration, code expiry/attempt limits, resend cooldown,
verification, and ordinary password login. Configured is not the same as delivered.

References:

- https://render.com/docs/free
- https://developers.google.com/workspace/gmail/api/guides/sending
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://developers.google.com/identity/protocols/oauth2
