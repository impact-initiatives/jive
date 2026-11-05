import contextvars
import gettext
import os
from _contextvars import Token

from argus.config import settings

# TODO: Add unique message ids so that messages in other languages
# can be identified?

# Context variable for the current locale string for fallback logic if needed
_current_locale: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_locale", default="en"
)


class I18nService:
    def __init__(self, domain: str = "messages"):
        self.domain: str = domain
        self.localedir: str = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
        self._cache: dict[str, gettext.NullTranslations] = {}

    def set_locale(self, locale: str) -> Token[str]:
        """Set locale for current request context."""

        token: Token[str] = _current_locale.set(locale)

        # Ensure translation is loaded
        if locale not in self._cache:
            try:
                trans = gettext.translation(
                    self.domain,
                    localedir=self.localedir,
                    languages=[locale],
                    fallback=True,  # Falls back to 'en' if file missing
                )
                self._cache[locale] = trans
            except Exception:
                # Fallback to default if specific locale fails
                self._cache[locale] = self._cache.get("en", gettext.NullTranslations())

        return token

    def reset_locale(self, token: Token[str]) -> None:
        _current_locale.reset(token)

    def _get_translator(self, locale: str):
        if locale not in self._cache:
            if len(self._cache) == 0:
                # this should only happen if set_locale was not initially set, ie in pytest modules
                _ = self.set_locale(locale)
            else:
                # Fallback
                self._cache[locale] = self._cache.get("en", gettext.NullTranslations())
        return self._cache[locale]

    def _(self, key: str, **kwargs: str | int | float) -> str:
        """
        Lookup message by key and format it.
        The 'key' passed here must match the 'msgid' in the .po file.
        if a key is not found for a given locale it falls back to the default locale (en)
        """
        current_locale = _current_locale.get()
        trans = self._get_translator(current_locale)
        template = trans.gettext(key)

        # Fallback to Fallback Locale (en))
        if template == key and current_locale != settings.FALLBACK_LOCALE:
            fallback_trans = self._get_translator(settings.FALLBACK_LOCALE)
            template = fallback_trans.gettext(key)

            #  if fallback also doesn't have it
            if template == key:
                # return the key
                pass

        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError:
                return f"[Error: Missing arg in {key}]"
        return template


i18n = I18nService()


def _(key: str, **kwargs: str | int | float) -> str:
    """Lookup message by key and format it."""
    return i18n._(key, **kwargs)
