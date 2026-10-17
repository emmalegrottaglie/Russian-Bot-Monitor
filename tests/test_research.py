from research import coordination as c

TEXT = "Breaking: this is the same message copied by several accounts at once"


def post(ts, author, text=TEXT, created=0, avatar=True):
    return {"ts": ts, "author": author, "norm": c.normalise(text), "author_created": created, "avatar": avatar}


def test_normalise_drops_links_mentions_and_punctuation():
    assert c.normalise("Hello, @someone.bsky.social! See https://x.example/a?b=1 NOW") == "hello see now"


def test_three_accounts_posting_the_same_text_together_form_a_cluster():
    posts = [post(1000, "a"), post(1005, "b", TEXT + "!!"), post(1008, "c"), post(1009, "d", "an unrelated post about the weather today")]
    assert c.coordinated(posts, 10) == {0, 1, 2}


def test_no_cluster_from_one_account_repeating_itself_or_from_slow_copies():
    same_author = [post(1000, "a"), post(1001, "a"), post(1002, "a")]
    assert c.coordinated(same_author, 60) == set()
    slow = [post(1000, "a"), post(1100, "b"), post(1200, "c")]
    assert c.coordinated(slow, 60) == set()
    assert c.coordinated(slow, 100) == {0, 1, 2}  # chained within the window


def test_short_texts_do_not_cluster():
    posts = [post(1000, a, "MAGA") for a in "abc"]
    assert c.coordinated(posts, 60) == set()


def test_hourly_totals_are_stamped_at_the_hour_end():
    day = 86400
    old = -100 * day
    posts = [post(3600 + 10, "a", created=3600 - day), post(3600 + 12, "b", created=old, avatar=False),
             post(3600 + 14, "c", created=old), post(7200, "d", "something else entirely, said once", created=old)]
    rows = c.hourly(posts, incomplete={10800})
    assert rows[0] == [7200, 4, 3, 3, 3, 1, 1, True]  # 7200 itself closes the first hour
    assert rows[1] == [10800, 0, 0, 0, 0, 0, 0, False]
