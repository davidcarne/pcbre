__author__ = 'davidc'


def get_consolidated_draws(dr):
    """
    Given a list dr of tuples (first, last), where first is inclusive, and last is exclusive,
    generate a list of consolidated ranges

    The intent is to minimize the number of draw calls necessary to render from a buffer

    :param dr: list[tuple[first, last]]
    :return:
    """
    if not dr:
        return []

    draw_ranges = sorted(dr)

    draw_ranges_consolidated = []
    current_first = draw_ranges[0][0]
    current_last = draw_ranges[0][1]

    for first, last in draw_ranges[1:]:
        if current_last == first:
            current_last = last
        else:
            draw_ranges_consolidated.append((current_first, current_last))
            current_first = first
            current_last = last

    draw_ranges_consolidated.append((current_first, current_last))

    return draw_ranges_consolidated


def get_consolidated_draws_1(dl):
    """
    Similar to get_consolidated_get_consolidated_draws, but for individual indicies
    :param dl:
    :return:
    """

    if not dl:
        return []

    dl = sorted(dl)

    consolidated = []

    current_first = dl[0]
    current_last = dl[0] + 1

    for current in dl[1:]:
        if current != current_last:
            consolidated.append((current_first, current_last))
            current_first = current

        current_last = current + 1

    consolidated.append((current_first, current_last))

    return consolidated
