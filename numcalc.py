from itertools import islice, product, zip_longest, combinations
ser = range(0, 18+19)
snt = range(0, 18+19)

def _specific_order_cartesian(lists):
    its = [[lst[0]] for lst in lists]
    yield tuple(lst[0] for lst in lists)

    for column in list(islice(zip_longest(*lists), 1, None)):
        for i, p in reversed(list(enumerate(column))):
            if p is None:
                continue

            yield from product(
                *(
                    (p,) if j == i else its[j]
                    for j in range(len(lists))
                )
            )

            its[i].append(p)


r = _specific_order_cartesian([ser, snt, ser, snt])

i = 0
for v in r:
    i += 1

print(i)
