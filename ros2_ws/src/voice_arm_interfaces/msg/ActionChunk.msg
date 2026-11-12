# VLA 输出的动作块
int32 chunk_size
int32 dof
float32[] actions              # 扁平化，长度 = chunk_size * dof
