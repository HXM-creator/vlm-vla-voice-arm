# VLM 输出的结构化任务指令
string action                  # pick_place | pick | place | stop
string target_color            # red | green | blue | any
string target_shape            # cube | cylinder | any
string target_ordinal          # leftmost | rightmost | middle | any
string target_description      # 自由文本描述
string destination_region      # left | right | center | any
string destination_relative_to
string reply                   # 语音播报文本
float32 confidence
bool need_clarify
string clarify_question
