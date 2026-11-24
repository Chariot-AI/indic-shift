# Security

Please report security problems privately through GitHub's "Report a vulnerability" button on the
Security tab of this repository rather than in a public issue.

Relevant areas include:

- **Control-token injection.** Indic Shift defines no special tokens: every input string is encoded as
  plain text, and ids 0..255 are reserved and never produced by `encode`. Any input that yields an id
  below 256, or that decodes to different text than it was encoded from, is a bug.
- **Untrusted ids.** `decode` and `StreamDecoder` accept arbitrary id sequences (for example model
  output). With `errors="replace"` they never raise on ids inside the vocabulary; malformed input
  becomes U+FFFD. Ids outside the vocabulary raise `ValueError`.
- **Data integrity.** The bundled tokenizer files are checked against sha256 values pinned in the
  package; a modified file raises `IntegrityError` when it loads.
