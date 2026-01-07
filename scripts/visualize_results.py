"""실험 결과 시각화 스크립트

3개 모드 (Vanilla, Current, Self-RAG) 비교 차트 생성
"""
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
import os

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 실험 결과 데이터 (docs/EXPERIMENT_RESULTS.md에서 가져옴)
EXPERIMENT_DATA = {
    "Vanilla RAG": {
        "avg_response_time": 14.4,
        "accuracy": 80,
        "recall_at_5": 0.75,
        "mrr": 0.82,
        "ndcg_at_3": 0.78,
        "color": "#3498db"
    },
    "Current (Agentic)": {
        "avg_response_time": 22.5,
        "accuracy": 100,
        "recall_at_5": 0.95,
        "mrr": 0.94,
        "ndcg_at_3": 0.92,
        "color": "#2ecc71"
    },
    "Self-RAG": {
        "avg_response_time": 80.7,
        "accuracy": 80,
        "recall_at_5": 0.72,
        "mrr": 0.80,
        "ndcg_at_3": 0.76,
        "color": "#e74c3c"
    }
}


def create_comparison_charts():
    """3가지 모드 비교 차트 생성"""
    output_dir = Path("docs/images")
    output_dir.mkdir(exist_ok=True, parents=True)

    modes = list(EXPERIMENT_DATA.keys())
    colors = [EXPERIMENT_DATA[mode]["color"] for mode in modes]

    # 1. 정확도 비교 (Accuracy, Recall@5, MRR, NDCG@3)
    fig, ax = plt.subplots(figsize=(10, 6))

    metrics = {
        "Accuracy (%)": [EXPERIMENT_DATA[mode]["accuracy"] for mode in modes],
        "Recall@5 (%)": [EXPERIMENT_DATA[mode]["recall_at_5"] * 100 for mode in modes],
        "MRR (%)": [EXPERIMENT_DATA[mode]["mrr"] * 100 for mode in modes],
        "NDCG@3 (%)": [EXPERIMENT_DATA[mode]["ndcg_at_3"] * 100 for mode in modes]
    }

    x = range(len(modes))
    width = 0.2

    for i, (metric_name, values) in enumerate(metrics.items()):
        ax.bar([pos + width * i for pos in x], values, width,
               label=metric_name, alpha=0.8)

    ax.set_ylabel('Score (%)', fontsize=12)
    ax.set_title('3개 모드 성능 비교: 정확도 지표', fontsize=14, fontweight='bold')
    ax.set_xticks([pos + width * 1.5 for pos in x])
    ax.set_xticklabels(modes)
    ax.legend(loc='lower right')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "mode_comparison_accuracy.png", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 정확도 비교 차트 생성: {output_dir / 'mode_comparison_accuracy.png'}")

    # 2. 응답 시간 비교
    fig, ax = plt.subplots(figsize=(8, 6))

    response_times = [EXPERIMENT_DATA[mode]["avg_response_time"] for mode in modes]
    bars = ax.bar(modes, response_times, color=colors, alpha=0.7)

    # 값 표시
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}s',
                ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax.set_ylabel('평균 응답 시간 (초)', fontsize=12)
    ax.set_title('3개 모드 응답 시간 비교', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "mode_comparison_response_time.png", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 응답 시간 비교 차트 생성: {output_dir / 'mode_comparison_response_time.png'}")

    # 3. 종합 비교 (Radar Chart)
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))

    categories = ['Accuracy', 'Recall@5', 'MRR', 'NDCG@3']
    num_vars = len(categories)

    angles = [n / float(num_vars) * 2 * 3.14159 for n in range(num_vars)]
    angles += angles[:1]

    for mode in modes:
        values = [
            EXPERIMENT_DATA[mode]["accuracy"] / 100,
            EXPERIMENT_DATA[mode]["recall_at_5"],
            EXPERIMENT_DATA[mode]["mrr"],
            EXPERIMENT_DATA[mode]["ndcg_at_3"]
        ]
        values += values[:1]

        ax.plot(angles, values, 'o-', linewidth=2, label=mode,
                color=EXPERIMENT_DATA[mode]["color"])
        ax.fill(angles, values, alpha=0.15, color=EXPERIMENT_DATA[mode]["color"])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'])
    ax.set_title('3개 모드 종합 성능 비교 (Radar Chart)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    ax.grid(True)

    plt.tight_layout()
    plt.savefig(output_dir / "mode_comparison_radar.png", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 종합 비교 차트 (Radar) 생성: {output_dir / 'mode_comparison_radar.png'}")

    # 4. 성능 vs 속도 Trade-off
    fig, ax = plt.subplots(figsize=(10, 6))

    for mode in modes:
        ax.scatter(
            EXPERIMENT_DATA[mode]["avg_response_time"],
            EXPERIMENT_DATA[mode]["accuracy"],
            s=300,
            color=EXPERIMENT_DATA[mode]["color"],
            alpha=0.6,
            edgecolors='black',
            linewidth=2,
            label=mode
        )

        # 모드 이름 표시
        ax.text(
            EXPERIMENT_DATA[mode]["avg_response_time"],
            EXPERIMENT_DATA[mode]["accuracy"] - 3,
            mode,
            ha='center',
            fontsize=10,
            fontweight='bold'
        )

    ax.set_xlabel('평균 응답 시간 (초)', fontsize=12)
    ax.set_ylabel('정확도 (%)', fontsize=12)
    ax.set_title('성능 vs 속도 Trade-off', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 90)
    ax.set_ylim(70, 105)

    # 이상적인 영역 표시
    ax.axhspan(95, 105, alpha=0.1, color='green', label='High Accuracy Zone')
    ax.axvspan(0, 30, alpha=0.1, color='blue', label='Fast Response Zone')

    ax.legend(loc='lower right')

    plt.tight_layout()
    plt.savefig(output_dir / "mode_comparison_tradeoff.png", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 성능 vs 속도 Trade-off 차트 생성: {output_dir / 'mode_comparison_tradeoff.png'}")

    print("\n🎉 모든 차트 생성 완료!")
    print(f"📁 저장 위치: {output_dir.absolute()}")


if __name__ == "__main__":
    create_comparison_charts()
