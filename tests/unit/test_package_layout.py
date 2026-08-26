def test_runtime_packages_are_importable():
    import memeradar_api
    import memeradar_domain
    import memeradar_providers
    import memeradar_worker

    assert memeradar_api.__version__
    assert memeradar_domain.__version__
    assert memeradar_providers.__version__
    assert memeradar_worker.__version__
