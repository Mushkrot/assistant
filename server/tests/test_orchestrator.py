"""Tests for the orchestrator module."""

import pytest
from app.services.orchestrator import is_question, TextAggregator
from app.models.events import Speaker, TranscriptDelta, TranscriptCompleted


class TestQuestionDetection:
    """Tests for question detection."""

    def test_question_mark(self):
        """Test detection of question mark."""
        assert is_question("What is your experience?")
        assert is_question("Can you tell me more?")
        assert is_question("Really?")

    def test_question_words(self):
        """Test detection of question words at start."""
        assert is_question("What do you think about this")
        assert is_question("How would you approach this problem")
        assert is_question("Why did you choose that solution")
        assert is_question("When did you start working on this")
        assert is_question("Where have you applied this before")
        assert is_question("Who was involved in the project")
        assert is_question("Which technology did you use")

    def test_invitation_phrases(self):
        """Test detection of invitation phrases."""
        assert is_question("Tell me about your experience")
        assert is_question("Can you explain how you did that")
        assert is_question("Could you walk me through the process")
        assert is_question("Describe your approach")
        assert is_question("Give me an example of that")

    def test_non_questions(self):
        """Test that statements are not detected as questions."""
        assert not is_question("I understand.")
        assert not is_question("That sounds great.")
        assert not is_question("We use Python for this.")
        assert not is_question("The system handles 1000 requests per second.")


class TestTextAggregator:
    """Tests for text aggregation."""

    def test_add_delta(self):
        """Test adding transcript deltas."""
        aggregator = TextAggregator()

        delta1 = TranscriptDelta(
            speaker=Speaker.THEM,
            text="Hello, ",
            segment_id="seg1",
            timestamp=1.0,
        )
        aggregator.add_delta(delta1)

        assert aggregator.pending_text == "Hello, "
        assert aggregator.pending_speaker == Speaker.THEM

        delta2 = TranscriptDelta(
            speaker=Speaker.THEM,
            text="how are you?",
            segment_id="seg1",
            timestamp=1.5,
        )
        aggregator.add_delta(delta2)

        assert aggregator.pending_text == "Hello, how are you?"

    def test_complete_segment(self):
        """Test completing a segment."""
        aggregator = TextAggregator()

        # Add delta first
        delta = TranscriptDelta(
            speaker=Speaker.THEM,
            text="Hello",
            segment_id="seg1",
            timestamp=1.0,
        )
        aggregator.add_delta(delta)

        # Complete the segment
        completed = TranscriptCompleted(
            speaker=Speaker.THEM,
            text="Hello, how are you?",
            segment_id="seg1",
            timestamp=2.0,
        )
        segment = aggregator.complete_segment(completed)

        assert segment is not None
        assert segment.text == "Hello, how are you?"
        assert segment.is_complete
        assert len(aggregator.history) == 1

    def test_get_last_context(self):
        """Test getting last context for speaker."""
        aggregator = TextAggregator()

        # Add completed segments
        for i, text in enumerate(["First message", "Second message", "Third message"]):
            completed = TranscriptCompleted(
                speaker=Speaker.THEM,
                text=text,
                segment_id=f"seg{i}",
                timestamp=float(i),
            )
            aggregator.complete_segment(completed)

        context = aggregator.get_last_context(Speaker.THEM, sentences=2)
        assert "Second message" in context
        assert "Third message" in context

    def test_word_count_trigger(self):
        """Test word count trigger."""
        aggregator = TextAggregator()

        # Add delta with many words
        delta = TranscriptDelta(
            speaker=Speaker.THEM,
            text="One two three four five six seven eight nine ten eleven twelve thirteen",
            segment_id="seg1",
            timestamp=1.0,
        )
        aggregator.add_delta(delta)

        assert aggregator.should_trigger_word_count()

    def test_word_count_no_trigger(self):
        """Test that short text doesn't trigger."""
        aggregator = TextAggregator()

        delta = TranscriptDelta(
            speaker=Speaker.THEM,
            text="Hello world",
            segment_id="seg1",
            timestamp=1.0,
        )
        aggregator.add_delta(delta)

        assert not aggregator.should_trigger_word_count()
