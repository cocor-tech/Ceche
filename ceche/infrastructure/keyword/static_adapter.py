from wordfreq import word_frequency

from ceche.domain.ports import KeywordPopularityPort


class StaticKeywordAdapter(KeywordPopularityPort):
    _REF_FREQ = 1e-3

    async def get_popularity(self, term: str) -> float:
        freq = word_frequency(term, "en")
        if freq <= 0:
            return 0.0
        score = min(100.0, max(0.0, freq / self._REF_FREQ * 70.0))
        return round(score, 2)
