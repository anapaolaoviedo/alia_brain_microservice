from nlp_pipeline import NlpPipeline

if __name__ == "__main__":
    # Initialize pipeline
    pipeline = NlpPipeline()

    # Test message
    test_text = """
    Hola, me interesa renovar mi póliza de seguro. 
    Mi número de póliza es ABC123456. 
    Mi carro es un Toyota Corolla 2020, 
    correo: usuario@correo.com, 
    teléfono: +5215548300145, 
    VIN: 1HGCM82633A123456
    """

    result = pipeline.process_message(test_text)

    print("\n🔍 Detected Intent:")
    print(result["intent"])

    print("\n📦 Extracted Entities:")
    for k, v in result["entities"].items():
        print(f"{k}: {v}")