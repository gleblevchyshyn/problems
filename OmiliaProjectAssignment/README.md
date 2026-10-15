# Natural Numbers Interpretation

A small console application that interprets a sequence of recognized numbers
(for example, the output of a speech recognizer) and lists every possible
phone number it could stand for, together with a Greek phone number validity check.

## Requirements

- Python 3.9 or newer (uses built-in generic types such as `set[str]`)
- No external dependencies

## How to run

```bash
python main.py
```

The program asks for input:

```
Enter numbers separated by spaces: 2 10 69 30 6 6 4
#    Output        Phone number
-------------------------------
1    21060930664   INVALID
2    2106093664    VALID
3    2106930664    VALID
4    210693664     INVALID
```

## Input format

- Numbers separated by one or more spaces.
- Each number has 1 to 3 digits, for example `0 0 30 69 700 24 1 3 50 2`.
- Invalid input (empty line, non-numeric tokens, tokens longer than 3 digits)
  prints a short error message instead of failing.
