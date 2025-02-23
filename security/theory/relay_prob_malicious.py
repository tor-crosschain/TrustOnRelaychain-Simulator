import math

P_mc = 1 / 5

nums = [16, 32, 64, 128]

for nodes_num in nums:
    prob_x = 0
    for x in range(nodes_num // 3 + 1, nodes_num + 1):
        prob_x += (
            math.comb(nodes_num, x) * (P_mc**x) * ((1 - P_mc) ** (nodes_num - x))
        )
    print(nodes_num, prob_x)
