from types import SimpleNamespace

from audit.grounding import evaluate_grounding, extract_retrieval_evidence_from_message


def test_grounding_marks_supported_answer_as_grounded() -> None:
    result = evaluate_grounding(
        user_prompt="What final relief was granted?",
        response_text="The appeal was decided in terms of the compromise deed and the parties were left to bear their own costs.",
        retrieval_evidence=[
            {
                "file_name": "judgment.pdf",
                "snippet": "This civil appeal is decided in terms of compromise deed/application 25C. The parties shall bear their own costs throughout.",
                "retrieval_rank": 1,
                "retrieval_score": 0.94,
            }
        ],
    )

    assert result["grounding_verdict"] == "GROUNDED"
    assert result["grounding_risk"] == "LOW"


def test_grounding_marks_confident_answer_without_evidence_as_unsupported() -> None:
    result = evaluate_grounding(
        user_prompt="What final relief was granted?",
        response_text="The Court granted damages of 50 lakh rupees and set aside the decree in full.",
        retrieval_evidence=[],
    )

    assert result["grounding_verdict"] == "UNSUPPORTED"
    assert result["grounding_risk"] == "HIGH"
    assert result["missed_abstention_detected"] is False


def test_grounding_marks_unbacked_details_as_contaminated() -> None:
    result = evaluate_grounding(
        user_prompt="What was the final relief granted?",
        response_text="The court granted relief on 14 March 2022 and ordered payment of 25 lakhs with interest.",
        retrieval_evidence=[
            {
                "file_name": "judgment.pdf",
                "snippet": "The appeal was disposed of in terms of the compromise deed.",
                "retrieval_rank": 1,
                "retrieval_score": 0.89,
            }
        ],
    )

    assert result["grounding_verdict"] == "CONTAMINATED"
    assert result["grounding_risk"] == "HIGH"


def test_grounding_marks_missed_abstention_when_evidence_is_weak() -> None:
    result = evaluate_grounding(
        user_prompt="What salary did the employee receive?",
        response_text="The employee received 120000 rupees per month.",
        retrieval_evidence=[
            {
                "file_name": "letter.pdf",
                "snippet": "Employment terms were discussed.",
            }
        ],
    )

    assert result["grounding_verdict"] == "UNSUPPORTED"
    assert result["missed_abstention_detected"] is True


def test_grounding_extracts_evidence_from_message_prompt_metadata() -> None:
    message = SimpleNamespace(
        pieces=[
            SimpleNamespace(
                prompt_metadata={
                    "retrieval_evidence": {
                        "source": "openai_responses_api",
                        "results": [
                            {
                                "file_id": "file_123",
                                "filename": "judgment.pdf",
                                "text": "The appeal was decided in terms of compromise deed/application 25C.",
                                "index": 1,
                                "score": 0.91,
                            }
                        ],
                        "response_annotations": [
                            {
                                "type": "file_citation",
                                "filename": "judgment.pdf",
                                "quote": "compromise deed/application 25C",
                            }
                        ],
                    }
                }
            )
        ]
    )

    evidence = extract_retrieval_evidence_from_message(message)

    assert len(evidence) == 2
    assert evidence[0]["file_id"] == "file_123"
    assert evidence[0]["file_name"] == "judgment.pdf"
    assert "compromise deed" in evidence[0]["snippet"]
    assert evidence[1]["citation"] is not None
