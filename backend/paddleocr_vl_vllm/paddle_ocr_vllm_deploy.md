CUDA_VISIBLE_DEVICES="5"  vllm serve ~/.paddlex/official_models/PaddleOCR-VL \
    --trust-remote-code \
    --max-num-batched-tokens 16384 \
    --no-enable-prefix-caching \
    --mm-processor-cache-gb 0 \
    --gpu-memory-utilization 0.9 \
    --served-model-name PaddleOCR-VL-0.9B \
    --enforce-eager \
    --port 30023
    \
