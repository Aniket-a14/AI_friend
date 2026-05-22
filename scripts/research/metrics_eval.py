import os
import re


def load_nrc_vad_lexicon():
    lexicon = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lexicon_path = os.path.join(script_dir, "NRC-VAD-Lexicon", "NRC-VAD-Lexicon.txt")
    if not os.path.exists(lexicon_path):
        print(f"⚠️ Warning: NRC-VAD Lexicon not found at {lexicon_path}")
        return lexicon
    try:
        with open(lexicon_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) == 4:
                    word = parts[0].lower()
                    try:
                        v = float(parts[1])
                        a = float(parts[2])
                        d = float(parts[3])
                        lexicon[word] = {"v": v, "a": a, "d": d}
                    except ValueError:
                        continue
    except Exception as e:
        print(f"⚠️ Error loading NRC-VAD Lexicon: {e}")
    return lexicon


class DualOracleScorer:
    """
    Implements a multi-dimensional emotional sentiment scorer mapping continuous Valence/Arousal
    using VADER compound scores merged with NRC-VAD valence/arousal averages.
    """

    def __init__(self):
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self.vader = SentimentIntensityAnalyzer()
        except ImportError:
            print("⚠️ vaderSentiment not found. Running with fallback sentiment model.")
            self.vader = None
        self.nrc_lexicon = load_nrc_vad_lexicon()

    def get_ground_truth(self, text: str) -> tuple:
        if not text:
            return 0.0, 0.5
        words = re.findall(r"\b[a-zA-Z]+\b", text.lower())

        valences = []
        arousals = []
        for word in words:
            if word in self.nrc_lexicon:
                valences.append(self.nrc_lexicon[word]["v"])
                arousals.append(self.nrc_lexicon[word]["a"])

        if valences:
            mean_v_nrc = sum(valences) / len(valences)
            nrc_valence_shifted = 2.0 * mean_v_nrc - 1.0  # Shift [0,1] to [-1,1]
            gt_arousal = sum(arousals) / len(arousals)
        else:
            nrc_valence_shifted = 0.0
            gt_arousal = 0.5

        if self.vader is not None:
            vader_scores = self.vader.polarity_scores(text)
            vader_compound = vader_scores["compound"]
        else:
            vader_compound = 0.0

        if valences:
            gt_valence = (vader_compound + nrc_valence_shifted) / 2.0
        else:
            gt_valence = vader_compound

        return gt_valence, gt_arousal
