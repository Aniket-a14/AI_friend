"""Tests for the self-directed grounding gate and the gap record behind it.

The pre-existing gate protects the *user's* facts ("you told me…"). This one is
its mirror: it stops the agent inventing concrete details about its own life --
siblings, hometowns, institutions, years -- that appear nowhere in its biography
or in the conversation.

Two failure directions matter, and they pull against each other. Letting a
fabrication through gives the user a confident false memory of a real person,
which is far harder to notice and undo than a blank. Firing on ordinary speech
makes the agent evasive about its own life, forces a regeneration, and costs a
cortisol burst every time. Most of these tests guard the second direction,
because that is the one a naive implementation gets wrong.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.action import ActionService
from app.state.conversation_store import ConversationHistoryStore
from app.state.self_knowledge_store import SelfKnowledgeStore

# Stands in for a seeded biography. Deliberately small: the gate must work from
# whatever the user actually wrote, not from a rich world model.
BIOGRAPHY_TERMS = {
    "daniel", "marcus", "elena", "coast", "riverside", "wren", "ada",
    "brother", "married", "december", "2025", "joint", "family",
}


@pytest.fixture
def agent():
    store = MagicMock()
    store.known_terms = BIOGRAPHY_TERMS
    return ActionService(self_knowledge=store)


@pytest.fixture
def ungrounded_agent():
    """An agent with no biography at all -- the cold-start case."""
    return ActionService()


@pytest.fixture
async def gap_store():
    store = ConversationHistoryStore()
    store.dsn = "sqlite:///:memory:"  # isolated per test; no shared app.db state
    await store.initialize()
    yield SelfKnowledgeStore(store.pool)
    await store.close()


class TestFabricationIsCaught:
    def test_invented_sibling_name_is_rejected(self, agent):
        """A brother the user never mentioned must not become part of her past.

        This is the whole point of the gate. An LLM asked about family will
        supply one, in character and without hedging, and the user has no way
        to tell it apart from a passage they wrote themselves.
        """
        ok, reason = agent._check_self_grounding(
            "My brother Rahul says the same thing.", [], ""
        )
        assert ok is False
        assert "own life" in reason

    def test_invented_hometown_is_rejected(self, agent):
        ok, _ = agent._check_self_grounding("I grew up in Delhi.", [], "")
        assert ok is False

    def test_invented_year_is_rejected(self, agent):
        """Dates are as inventable as names, and read as far more authoritative."""
        ok, _ = agent._check_self_grounding("I was born in 1998.", [], "")
        assert ok is False

    def test_invented_institution_is_rejected(self, agent):
        ok, _ = agent._check_self_grounding(
            "I studied at IIT Bombay before this.", [], ""
        )
        assert ok is False

    def test_a_possession_nobody_thought_to_list_is_still_gated(self, agent):
        """The trigger is grammatical, so it cannot miss a kind of life.

        An earlier version enumerated the possessed nouns -- brother, hometown,
        school -- so "my dog Jolly" sailed through while "my brother Rahul" was
        caught. The gate then protected only the lives its author happened to
        imagine, and every biography is a different life. "my" generalises;
        a noun list is a guess about someone else's family.
        """
        ok, _ = agent._check_self_grounding(
            "My dog Jolly waits by the door.", [], ""
        )
        assert ok is False

    def test_the_ungrounded_terms_are_returned_for_recording(self, agent):
        """The gap list is what makes the biography's holes visible later."""
        gaps = agent._self_claim_gaps("My brother Rahul lives in Mumbai.", [], "")
        assert set(gaps) == {"rahul", "mumbai"}


class TestTruthIsNotBlocked:
    def test_biography_sibling_is_allowed(self, agent):
        """The agent must be able to talk about the family it actually has.

        If this fails, the gate has made her unable to say true things about
        her own life, which is a worse outcome than the fabrication it was
        built to prevent -- it would be visible in every single conversation.
        """
        ok, _ = agent._check_self_grounding(
            "My brother Daniel is three years younger than me.", [], ""
        )
        assert ok is True

    def test_grounding_does_not_depend_on_what_surfaced_this_turn(self, agent):
        """Retrieval returns what is relevant, not everything the agent knows.

        Grounding self-claims against the surfaced memories alone would reject
        true statements whenever the relevant passage happened not to surface,
        which is most turns. The biography vocabulary is the fix; this test is
        what proves it is actually being consulted.
        """
        ok, _ = agent._check_self_grounding("I grew up on the coast.", [], "")
        assert ok is True

    def test_a_fact_from_the_current_message_is_grounded(self, ungrounded_agent):
        """What the user just said counts, even with no biography loaded."""
        ok, _ = ungrounded_agent._check_self_grounding(
            "My cousin Elena, yes.", [], "how is your cousin Elena doing"
        )
        assert ok is True

    def test_a_fact_from_a_surfaced_memory_is_grounded(self, ungrounded_agent):
        ok, _ = ungrounded_agent._check_self_grounding(
            "My cousin Elena called.",
            [{"content": "Elena is her cousin"}],
            "",
        )
        assert ok is True


class TestOrdinarySpeechIsNotGated:
    def test_feelings_about_family_are_not_a_factual_claim(self, agent):
        """"My family means everything to me" invents nothing.

        The user-directed gate fires on two unsupported words, which this
        sentence has. Reusing that rule here would make the agent unable to
        express affection for her own family without a regeneration.
        """
        ok, _ = agent._check_self_grounding(
            "My family means everything to me, always.", [], ""
        )
        assert ok is True

    def test_preferences_are_not_gated(self, agent):
        """Tastes are half of a personality; gating them makes the agent flat."""
        ok, _ = agent._check_self_grounding("I love rasgulla, obviously.", [], "")
        assert ok is True

    def test_a_sentence_opening_with_a_capital_is_not_a_name(self, agent):
        """Sentence case is not evidence of a proper noun.

        Without the first-position exemption every self-claim sentence would
        indict itself on its own opening word.
        """
        ok, _ = agent._check_self_grounding(
            "Delhi is far from my hometown anyway.", [], ""
        )
        assert ok is True

    def test_a_capitalised_common_noun_is_not_a_name(self, agent):
        """Capitalisation alone is not identity.

        Models capitalise for emphasis and in title case. "My School" names no
        institution, and treating the trigger word itself as the fabricated
        specific would make the gate indict every claim it examines.
        """
        ok, _ = agent._check_self_grounding("My School was strict about it.", [], "")
        assert ok is True

    def test_the_possessed_noun_is_never_the_fabrication(self, agent):
        """Whatever follows "my" fired the gate; it cannot also be the evidence.

        This has to hold for any noun, not the ones a stopword list happened to
        name -- otherwise the pattern and its exemption drift apart, and the
        first noun added to one and forgotten in the other makes the gate
        reject a sentence for containing its own trigger.
        """
        ok, _ = agent._check_self_grounding(
            "My Landlord raised the rent again.", [], ""
        )
        assert ok is True

    def test_a_first_person_verb_is_never_the_fabrication(self, agent):
        """The same exemption, on the other half of the pattern."""
        ok, _ = agent._check_self_grounding("I Studied hard for it.", [], "")
        assert ok is True

    def test_a_contraction_of_i_is_not_a_name(self, agent):
        """"I've" is capitalised, three letters long, and refers to nobody."""
        ok, _ = agent._check_self_grounding(
            "My family, I've said, is everything.", [], ""
        )
        assert ok is True

    def test_a_response_with_no_self_claim_is_never_examined(self, agent):
        """The trigger phrase is required, exactly as in the user-facing gate."""
        ok, _ = agent._check_self_grounding(
            "That sounds really hard. Rahul from work would say the same.", [], ""
        )
        assert ok is True


class TestCompositeGate:
    def test_the_user_directed_gate_still_fires(self, agent):
        """Composition must not have disabled the gate that already existed."""
        ok, reason = agent._check_response_grounding(
            "You told me your dog Rex loved the beach at Brighton.", [], ""
        )
        assert ok is False
        assert "SHARED HISTORY" in reason

    def test_the_self_gate_fires_through_the_composite(self, agent):
        """Every existing call site gains the new check by composition alone."""
        ok, _ = agent._check_response_grounding("My sister Neha agrees.", [], "")
        assert ok is False

    def test_a_clean_response_passes_both(self, agent):
        ok, reason = agent._check_response_grounding(
            "That sounds lovely, honestly.", [], ""
        )
        assert ok is True
        assert reason == ""


class TestGapRecording:
    @pytest.mark.asyncio
    async def test_repeated_gaps_accumulate_hits(self, gap_store):
        """Frequency is the signal for what the biography most needs.

        A name that comes up constantly and is never grounded matters more than
        a one-off, and only a running count can tell them apart.
        """
        await gap_store.record_gap(["rahul"], "who is rahul")
        await gap_store.record_gap(["rahul"], "rahul again")
        gaps = await gap_store.top_gaps()
        assert len(gaps) == 1
        assert gaps[0]["term"] == "rahul"
        assert gaps[0]["times_hit"] == 2

    @pytest.mark.asyncio
    async def test_gaps_are_ranked_by_how_often_they_come_up(self, gap_store):
        await gap_store.record_gap(["mumbai"], "x")
        for _ in range(3):
            await gap_store.record_gap(["rahul"], "x")
        gaps = await gap_store.top_gaps()
        assert [g["term"] for g in gaps] == ["rahul", "mumbai"]

    @pytest.mark.asyncio
    async def test_one_response_cannot_flood_the_table(self, gap_store):
        """A single bad generation must not bury the genuinely frequent gaps."""
        written = await gap_store.record_gap([f"term{i}" for i in range(50)], "x")
        assert written == 8

    @pytest.mark.asyncio
    async def test_recording_survives_a_broken_pool(self):
        """The turn has already been stopped from lying; losing the note is cheap.

        Raising here would turn a correctly-caught fabrication into a failed
        conversation, which is strictly worse than an unrecorded gap.
        """
        pool = MagicMock()
        pool.acquire.side_effect = RuntimeError("database is gone")
        store = SelfKnowledgeStore(pool)
        assert await store.record_gap(["rahul"], "x") == 0

    @pytest.mark.asyncio
    async def test_the_action_service_records_what_it_rejected(self):
        """The gate and the record must see the same terms.

        If these drift apart the biography's holes stop being visible, and the
        only signal left is the user noticing the agent going quiet.
        """
        recorder = AsyncMock()
        recorder.known_terms = set()
        service = ActionService(self_knowledge=recorder)
        await service._record_self_gaps("My brother Rahul called.", [], "hi")
        recorder.record_gap.assert_awaited_once()
        assert set(recorder.record_gap.await_args.args[0]) == {"rahul"}

    @pytest.mark.asyncio
    async def test_nothing_is_recorded_without_a_store(self):
        """The gate stays functional when the store was never wired in."""
        service = ActionService()
        await service._record_self_gaps("My brother Rahul called.", [], "")


class TestKnownTerms:
    @pytest.mark.asyncio
    async def test_only_biography_memories_ground_the_agents_own_past(self):
        """Conversational memories must not become evidence for autobiography.

        Ordinary memories are things the *user* said. If they counted as
        grounding, one hallucinated detail that reached the memory store would
        become the justification for the next -- the gate would ratify its own
        escapes.
        """
        conn = AsyncMock()
        conn.fetch.return_value = [{"content": "she grew up on the coast"}]
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        store = SelfKnowledgeStore(pool)
        await store.refresh_known_terms()

        assert conn.fetch.await_args.args[1] == "biography"
        assert "coast" in store.known_terms

    @pytest.mark.asyncio
    async def test_the_agents_own_name_is_grounded_without_a_biography(self):
        """A third-person biography never contains the name of its subject.

        "She talks calmly…" describes her without ever naming her, so without
        an explicit seed the agent stating its own name reads as an ungrounded
        claim about a stranger.
        """
        store = SelfKnowledgeStore(None, seed_terms={"Ada"})
        assert "ada" in store.known_terms
