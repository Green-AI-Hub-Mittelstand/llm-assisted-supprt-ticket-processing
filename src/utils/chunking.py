
def naive_chunking(text:list, overlap:bool=True) -> dict:
    '''
        Unites text based on heading '##' tags and max_length. 
        Optional overlapping splitted paragraphs (overlap=True).

        Args: 
            text (list): Input text from preprocessing step.

        Returns: 
            dict: of final chunks as keys, page numbers as values.
    '''

    current_string = ""
    last_str = ""
    max_len = 2500
    page_num = None
    output_dict = {}

    # interate through list to access sets
    for t, n in text:
        # test for header
        if len(t) > 1 and t[0:1] == "#":
            if page_num is not None:
                output_dict[current_string] = page_num
            current_string = t
            page_num = n
        else:
            # if max_length not reached: append string, update page_num
            if len(current_string) + len(t) <= max_len:
                current_string += f' {t}'
                last_str = t
                if page_num is None or n < page_num:
                    page_num = n
            # else: add section to dict, start with string, page_num
            else:
                output_dict[current_string] = page_num
                current_string = f'{last_str} {t}' if overlap else t
                page_num = n

    # add last section to dict
    output_dict[current_string] = page_num
    output = []
    for k, v in output_dict.items():
        output.append({
            "text": k,
            "page_no": v
        })

    return output
