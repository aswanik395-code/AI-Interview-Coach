from scoring import normalize_eval, score_answer, score_interview, rating_for


def ev(c, d, cl, flag=False):
    return normalize_eval({"correctness": c, "depth": d, "clarity": cl, "red_flag": flag})


def test_perfect_and_zero():
    assert score_answer(ev(10, 10, 10)) == 100.0
    assert score_answer(ev(0, 0, 0)) == 0.0


def test_weights():
    assert score_answer(ev(10, 0, 0)) == 50.0
    assert score_answer(ev(0, 10, 0)) == 30.0
    assert score_answer(ev(0, 0, 10)) == 20.0


def test_red_flag_penalty_floor():
    assert score_answer(ev(10, 10, 10, True)) == 90.0
    assert score_answer(ev(0, 0, 0, True)) == 0.0


def test_garbage_input_is_clamped():
    e = normalize_eval({"correctness": "99", "depth": -4, "clarity": "abc", "strengths": "nope"})
    assert (e["correctness"], e["depth"], e["clarity"]) == (10, 0, 0)
    assert e["strengths"] == []
    assert normalize_eval(None)["correctness"] == 0


def test_skipped_counts_as_zero():
    r = score_interview([ev(10, 10, 10), normalize_eval(None, skipped=True)])
    assert r["overall"] == 50.0 and r["skipped"] == 1 and r["answered"] == 1


def test_overall_is_deterministic():
    evals = [ev(8, 6, 7), ev(5, 4, 6), ev(9, 8, 8)]
    assert score_interview(evals) == score_interview(evals)


def test_bands():
    assert rating_for(90) == "Strong" and rating_for(70) == "Good"
    assert rating_for(55) == "Borderline" and rating_for(10) == "Needs improvement"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("pass", name)