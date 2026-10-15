def number_validation(input_text: str) -> bool:
    input_text = "".join(input_text.split())
    if not (input_text.isascii() and input_text.isdigit()):
        return False
    
    if len(input_text) == 10:
        return input_text.startswith(("2", "69"))
    elif len(input_text) == 14:
        return input_text.startswith(("00302", "003069"))

    else:
        return False


# NOTE: The output/formatting part below (is_valid_input, print_table, main)
# was generated with AI assistance (Claude) and reviewed by me.
# The core logic (token_variants, possible_interpretations, number_validation)
# was written by me.

def token_variants(token: str) -> set[str]:
    number = int(token)
    if number < 10:
        return {token}
    if number > 20 and number < 100:
        return {token}  if number % 10 == 0 else {token, token[0] + "0" + token[1]} 
    if number > 100 and number < 1000:
        return {token} if number % 100 == 0 else {token} | {str((number // 100)*100) + element for element in token_variants(str(number % 100))}
    
    return {token}


def possible_interpretations(input_text: str) -> set[str]:
    input_text = input_text.strip()
    
    if len(input_text) == 0:
        return {""}
    
    tokens = input_text.split()
    prefixes = token_variants(tokens[0])
    
    number = int(tokens[0])
    
    result = {prefix + suffix for prefix in prefixes for suffix in possible_interpretations(input_text[len(tokens[0]) + 1:])}
    if len(tokens) > 1:
        next_token_idx = sum([len(element) for element in tokens[:2]])
        if number >= 20 and number < 100 and number % 10 == 0 and len(tokens[1]) == 1:
            result |= {str(int(tokens[1]) + number) + element for element in possible_interpretations(input_text[next_token_idx + 1:])}
        if number >= 100 and number < 1000 and number % 100 == 0 and len(tokens[1]) < 3:
            result |= {str(number + int(tokens[1])) + element for element in possible_interpretations(input_text[next_token_idx + 1:])}
    
    return result
    
def is_valid_input(text: str) -> bool:
    tokens = text.split()
    return bool(tokens) and all(
        t.isascii() and t.isdigit() and len(t) <= 3 for t in tokens
    )


def print_table(text: str) -> None:
    variants = sorted(possible_interpretations(text))
    width = max(len("Output"), *(len(v) for v in variants))

    print(f"{'#':<5}{'Output':<{width + 3}}{'Phone number'}")
    print("-" * (5 + width + 3 + len("Phone number")))

    for i, variant in enumerate(variants, start=1):
        status = "VALID" if number_validation(variant) else "INVALID"
        print(f"{i:<5}{variant:<{width + 3}}{status}")


def main() -> None:
    text = input("Enter numbers separated by spaces: ")
    if not is_valid_input(text):
        print("Invalid input: use numbers of up to three digits separated by spaces.")
        return
    print_table(text)


if __name__ == "__main__":
    main()