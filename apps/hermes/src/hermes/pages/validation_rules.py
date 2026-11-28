"""Reference page listing all validation-rule documentation by section."""

import re

import streamlit as st

from hermes.common import (
    SEVERITY_HELP,
    SEVERITY_ORDER,
    build_rules_index,
    build_severity_badge,
    load_rule_doc,
    load_rules_readme,
    rule_display,
)

# --- overview readme -----------------------------------------------------------------

readme = load_rules_readme()
if readme:
    st.markdown(readme)


st.markdown("**Validation Result Severities**")
for severity in SEVERITY_ORDER:
    st.markdown(f"{build_severity_badge(severity)} - {SEVERITY_HELP[severity]}")

# --- search -----------------------------------

search = st.text_input("Search rule documentation", placeholder="e.g. rule name…")

index = build_rules_index()
if not index:
    st.info("No rule documentation found.")
    st.stop()

# --- filtering ------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Anchor-safe slug for heading links (rule names are unique by design)."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def rule_matches(rule_name: str, doc: str | None, search_text: str) -> bool:
    """True when the rule name or its documentation matches the search text."""
    if not search_text:
        return True
    pattern = f"(?i){re.escape(search_text)}"
    return bool(re.search(pattern, rule_name) or (doc and re.search(pattern, doc)))


visible: dict[str, list[tuple[str, str | None]]] = {}
for folder, names in sorted(index.items()):
    matched = []
    for name in names:
        doc = load_rule_doc(name)
        title, body = rule_display(name, doc)
        if rule_matches(name, doc, search):
            matched.append((title, body))
    if matched:
        visible[folder] = matched

if search and not visible:
    st.info(f"No rule documentation matches “{search}”.")
    st.stop()

# --- table of contents -----------------------------------------------------------------

toc_lines = []
for folder, matched in visible.items():
    toc_lines.append(
        f"- [{folder.title() if folder else 'General'}](#{slugify(folder or 'general')})"
    )
    for name, _doc in matched:
        toc_lines.append(f"  - [{name}](#{slugify(name)})")
st.markdown("\n".join(toc_lines))

# --- sections -----------------------------------------------------------------------------

for folder, matched in visible.items():
    st.header(folder.title() if folder else "General", anchor=slugify(folder or "general"))
    st.divider()
    for title, body in matched:
        st.subheader(title, anchor=slugify(title))
        if body:
            st.markdown(body)
        else:
            st.caption("No documentation file found for this rule.")
        st.divider()
