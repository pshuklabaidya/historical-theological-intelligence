# Witnesses and Collation

Register a witness before searching or collating it. Record `witness_id`, `work_id`, witness type, edition or translation relationship, source, locator, access status, and independence group. The witness graph may include page images, transcriptions, later editions, translations, quotations, and indirect witnesses; label directed relations such as `same_setting_as`, `derived_from`, `translation_of`, `quotes`, `corrects`, and `unknown_relation`.

The supplied page is always the controlling observational witness. Report:

- visible supplied-page reading;
- normalized reading;
- another witness's reading;
- reconstruction or editorial choice;
- effect on translation.

Use `python scripts/search_witness.py --registry witness-registry.json --witness-id WITNESS-ID QUERY` for explicitly registered text. Use `python scripts/collate.py SUPPLIED.txt COMPARISON.txt --a-label supplied --b-label comparison`; `--ignore-orthography` ignores configured u/v, i/j, ligature, case, and punctuation variation but must not hide substantive variants.

## Scholar View requirement

For Scholar View, `witness_comparison` means comparison against at least one independently inspected textual witness when an accessible comparator can be found and external research has not been declined. A variant reported inside the supplied page is not a second witness. If no witness is already registered and research access is available, attempt discovery, register the comparator before collation, and inspect the relevant passage directly. If discovery or access fails, record the limitation and continue without fabricating a comparison.
