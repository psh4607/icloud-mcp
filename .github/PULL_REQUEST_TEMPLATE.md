## Summary

<!-- What does this PR do and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / internal change
- [ ] Other:

## Testing

<!-- How did you verify this? -->

- [ ] `pytest` passes locally
- [ ] Added/updated tests for the change
- [ ] N/A (docs only)

## Security checklist

<!-- This server handles iCloud credentials and can send mail / mutate
     calendar & contacts. Please confirm: -->

- [ ] No secrets, app-specific passwords, emails, or tokens added to code, tests, or fixtures (placeholders only)
- [ ] Read paths remain read-only (no unintended mutations)
- [ ] Any new write/mutating tool is gated behind `ICLOUD_ENABLE_WRITES` **and** a per-action confirmation, consistent with existing write tools
- [ ] N/A

## Notes for the reviewer

<!-- Anything you want me to look at closely, trade-offs, follow-ups. -->
