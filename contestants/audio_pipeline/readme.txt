check out the  tests/test_localized_narrators.py for usage in script. 

basic use below pattern for generation of ssml for tts call. 

    factory = CandidateNarratorFactory()
    narrator = factory.create("hi")
    entity = _sample_entity()

    segments = narrator.ssml_segments(entity)