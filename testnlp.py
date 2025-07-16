from nlp_pipeline import NlpPipeline

if __name__ == "__main__":
    # Initialize pipeline
    pipeline = NlpPipeline()

    # Test message
    test_text = """
    how can i just like the insurance to cancelate?
    """

    result = pipeline.process_message(test_text)

    print("\n🔍 Detected Intent:")
    print(result["intent"])

    print("\n📦 Extracted Entities:")
    for k, v in result["entities"].items():
        print(f"{k}: {v}")