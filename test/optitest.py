import csv
import math
from scipy import optimize

data = []

def cost(i):
    i = math.floor(abs(x))
    #print(data[i][1])
    return float(data[i][1])

def f(x):
    return x**2


def main():
    with open('test3.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                data.append(row)

main()
minimum = optimize.fmin(cost, 50)
print(minimum)
