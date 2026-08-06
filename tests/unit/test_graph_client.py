from frontend import graph_client


def _fresh(tmp_path):
    g = graph_client.make_graph(db_path=str(tmp_path / "t.db"), force_stubs=True)
    cfg = graph_client.new_thread_config()
    return g, cfg


def test_start_pauses_at_human_approval(tmp_path):
    g, cfg = _fresh(tmp_path)
    list(graph_client.start_run(g, cfg, "Acme", "https://acme.test"))
    values, next_nodes, payload = graph_client.snapshot(g, cfg)
    assert next_nodes == ("human_approval",)
    assert payload is not None
    assert payload["company_name"] == "Acme"
    assert values["screening_decision"] == "pass"   # screen_stub always passes


def test_resume_approved_runs_to_memo(tmp_path):
    g, cfg = _fresh(tmp_path)
    list(graph_client.start_run(g, cfg, "Acme", "https://acme.test"))
    list(graph_client.resume_run(g, cfg, approved=True))
    values, next_nodes, payload = graph_client.snapshot(g, cfg)
    assert next_nodes == ()          # run finished
    assert payload is None
    assert values["memo_base"]       # write_memo stub wrote something


def test_resume_not_approved_ends_run(tmp_path):
    g, cfg = _fresh(tmp_path)
    list(graph_client.start_run(g, cfg, "Acme", "https://acme.test"))
    list(graph_client.resume_run(g, cfg, approved=False))
    values, next_nodes, _ = graph_client.snapshot(g, cfg)
    assert next_nodes == ()
    assert values["memo_base"] == ""  # specialists never ran


def test_new_thread_configs_are_unique():
    a = graph_client.new_thread_config()
    b = graph_client.new_thread_config()
    assert a["configurable"]["thread_id"] != b["configurable"]["thread_id"]
