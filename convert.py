import torch
import onnx
import onnxsim


# ========== 导出支持动态batch和动态长度的ONNX ==========
def export_asr_dynamic(model, onnx_path):
    """
    导出支持动态维度的语音识别模型
    """
    model.eval()

    # 示例输入：batch=1, 10秒音频(16kHz)
    dummy_input = torch.randn(1, 160000)

    with torch.no_grad():
        torch.onnx.export(
            model,
            dummy_input,
            onnx_path,
            input_names=["audio"],
            output_names=["transcription"],
            opset_version=11,
            do_constant_folding=True,
            # 🔑 关键：设置动态维度
            dynamic_axes={
                "audio": {
                    0: "batch_size",  # 可以一次处理多个音频
                    1: "audio_length",  # 支持不同长度的音频
                },
                "transcription": {
                    0: "batch_size",
                    1: "text_length",  # 输出文本长度也可变
                },
            },
        )

    print(f"✓ 动态ONNX已导出: {onnx_path}")

    # 简化模型
    original = onnx.load(onnx_path)
    simplified, check = onnxsim.simplify(original)
    if check:
        onnx.save(simplified, onnx_path.replace(".onnx", "_sim.onnx"))
        print(f"✓ 简化完成")


# ========== 验证动态功能 ==========
import onnxruntime as ort
import numpy as np


def test_dynamic_batch(onnx_path):
    """测试不同batch size和音频长度"""
    session = ort.InferenceSession(onnx_path)

    # 测试不同场景
    test_cases = [
        (1, 160000),  # 1个音频，10秒
        (2, 160000),  # 2个音频，10秒
        (1, 80000),  # 1个音频，5秒（不同长度）
        (4, 320000),  # 4个音频，20秒
    ]

    for batch, length in test_cases:
        audio = np.random.randn(batch, length).astype(np.float32)
        try:
            output = session.run(None, {"audio": audio})
            print(f"✓ Batch={batch}, Length={length}: output shape={output[0].shape}")
        except Exception as e:
            print(f"✗ Batch={batch}, Length={length}: {e}")


# 使用
# export_asr_dynamic(your_model, 'asr_dynamic.onnx')
# test_dynamic_batch('asr_dynamic_sim.onnx')
