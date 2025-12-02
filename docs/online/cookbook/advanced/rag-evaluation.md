# RAG 效果评估

本教程讲解如何评估和优化基于 Unifiles 构建的 RAG（检索增强生成）系统的效果。

## 评估框架概述

```
RAG 评估维度：
├── 检索质量 (Retrieval Quality)
│   ├── 召回率 (Recall)
│   ├── 精确率 (Precision)
│   └── MRR (Mean Reciprocal Rank)
├── 生成质量 (Generation Quality)
│   ├── 答案相关性
│   ├── 事实准确性
│   └── 完整性
└── 端到端效果 (End-to-End)
    ├── 用户满意度
    └── 任务完成率
```

## 检索质量评估

### 构建评估数据集

```python
from dataclasses import dataclass
from typing import List

@dataclass
class RetrievalTestCase:
    query: str
    relevant_doc_ids: List[str]  # 标注的相关文档
    description: str = ""

# 创建测试数据集
test_cases = [
    RetrievalTestCase(
        query="年假申请流程是什么？",
        relevant_doc_ids=["doc_hr_001", "doc_hr_002"],
        description="年假相关查询"
    ),
    RetrievalTestCase(
        query="报销需要哪些材料？",
        relevant_doc_ids=["doc_finance_001"],
        description="报销相关查询"
    ),
    RetrievalTestCase(
        query="如何申请远程办公？",
        relevant_doc_ids=["doc_hr_005", "doc_it_001"],
        description="远程办公相关查询"
    ),
]
```

### 计算检索指标

```python
from unifiles import UnifilesClient
from typing import List, Dict
import numpy as np

client = UnifilesClient(api_key="sk_...")

def evaluate_retrieval(
    kb_id: str,
    test_cases: List[RetrievalTestCase],
    top_k: int = 5
) -> Dict:
    """评估检索质量"""
    
    metrics = {
        "recall": [],
        "precision": [],
        "mrr": [],
        "hit_rate": []
    }
    
    for case in test_cases:
        # 执行搜索
        results = client.knowledge_bases.search(
            kb_id=kb_id,
            query=case.query,
            top_k=top_k
        )
        
        retrieved_ids = [chunk.document_id for chunk in results.chunks]
        relevant_ids = set(case.relevant_doc_ids)
        
        # 计算召回率
        hits = len(set(retrieved_ids) & relevant_ids)
        recall = hits / len(relevant_ids) if relevant_ids else 0
        metrics["recall"].append(recall)
        
        # 计算精确率
        precision = hits / len(retrieved_ids) if retrieved_ids else 0
        metrics["precision"].append(precision)
        
        # 计算 MRR
        mrr = 0
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                mrr = 1 / (i + 1)
                break
        metrics["mrr"].append(mrr)
        
        # 命中率
        hit = 1 if hits > 0 else 0
        metrics["hit_rate"].append(hit)
    
    # 计算平均值
    return {
        "avg_recall": np.mean(metrics["recall"]),
        "avg_precision": np.mean(metrics["precision"]),
        "avg_mrr": np.mean(metrics["mrr"]),
        "hit_rate": np.mean(metrics["hit_rate"]),
        "num_cases": len(test_cases)
    }

# 评估
results = evaluate_retrieval(kb_id, test_cases, top_k=5)
print(f"召回率: {results['avg_recall']:.2%}")
print(f"精确率: {results['avg_precision']:.2%}")
print(f"MRR: {results['avg_mrr']:.3f}")
print(f"命中率: {results['hit_rate']:.2%}")
```

### 分块策略对比评估

```python
def compare_chunking_strategies(
    file_ids: List[str],
    test_cases: List[RetrievalTestCase],
    strategies: List[Dict]
) -> Dict:
    """对比不同分块策略的效果"""
    
    results = {}
    
    for strategy in strategies:
        # 创建知识库
        kb = client.knowledge_bases.create(
            name=f"eval_{strategy['name']}",
            chunking_strategy=strategy["config"]
        )
        
        # 添加文档
        for file_id in file_ids:
            doc = client.knowledge_bases.documents.create(
                kb_id=kb.id,
                file_id=file_id
            )
            doc.wait()
        
        # 评估
        metrics = evaluate_retrieval(kb.id, test_cases)
        results[strategy["name"]] = metrics
        
        # 清理
        client.knowledge_bases.delete(kb.id)
    
    return results

# 对比策略
strategies = [
    {"name": "small_fixed", "config": {"type": "fixed", "chunk_size": 256}},
    {"name": "medium_semantic", "config": {"type": "semantic", "chunk_size": 512}},
    {"name": "large_semantic", "config": {"type": "semantic", "chunk_size": 1024}},
]

comparison = compare_chunking_strategies(file_ids, test_cases, strategies)

for name, metrics in comparison.items():
    print(f"\n{name}:")
    print(f"  召回率: {metrics['avg_recall']:.2%}")
    print(f"  MRR: {metrics['avg_mrr']:.3f}")
```

## 生成质量评估

### 使用 LLM 评估答案质量

```python
from openai import OpenAI

openai = OpenAI(api_key="sk_openai_...")

@dataclass
class QATestCase:
    question: str
    reference_answer: str  # 标准答案
    context_doc_ids: List[str]

def evaluate_answer_quality(
    question: str,
    generated_answer: str,
    reference_answer: str
) -> Dict:
    """使用 LLM 评估答案质量"""
    
    prompt = f"""评估生成答案的质量，与参考答案对比。

问题：{question}

参考答案：{reference_answer}

生成答案：{generated_answer}

请从以下维度评分（1-5分）并说明理由：
1. 相关性：答案是否回答了问题
2. 准确性：答案是否事实正确
3. 完整性：答案是否完整覆盖问题
4. 简洁性：答案是否简明扼要

输出 JSON 格式：
{{"relevance": 分数, "accuracy": 分数, "completeness": 分数, "conciseness": 分数, "reasoning": "评估理由"}}
"""
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def evaluate_rag_pipeline(
    kb_id: str,
    test_cases: List[QATestCase],
    llm_model: str = "gpt-4"
) -> Dict:
    """评估完整 RAG 管道"""
    
    scores = {
        "relevance": [],
        "accuracy": [],
        "completeness": [],
        "conciseness": []
    }
    
    for case in test_cases:
        # 检索
        results = client.knowledge_bases.search(
            kb_id=kb_id,
            query=case.question,
            top_k=5
        )
        
        context = "\n\n".join([c.content for c in results.chunks])
        
        # 生成
        generated = generate_answer(case.question, context, llm_model)
        
        # 评估
        eval_result = evaluate_answer_quality(
            case.question,
            generated,
            case.reference_answer
        )
        
        for key in scores:
            scores[key].append(eval_result.get(key, 0))
    
    return {
        "avg_relevance": np.mean(scores["relevance"]),
        "avg_accuracy": np.mean(scores["accuracy"]),
        "avg_completeness": np.mean(scores["completeness"]),
        "avg_conciseness": np.mean(scores["conciseness"]),
        "overall": np.mean([np.mean(v) for v in scores.values()])
    }

def generate_answer(question: str, context: str, model: str) -> str:
    """基于上下文生成答案"""
    
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "基于提供的上下文回答问题。如果上下文不包含答案，说明无法回答。"
            },
            {
                "role": "user",
                "content": f"上下文：\n{context}\n\n问题：{question}"
            }
        ]
    )
    
    return response.choices[0].message.content
```

## 自动化评估流水线

```python
import json
from datetime import datetime
from pathlib import Path

class RAGEvaluator:
    """RAG 评估器"""
    
    def __init__(self, unifiles_client, openai_client, kb_id: str):
        self.unifiles = unifiles_client
        self.openai = openai_client
        self.kb_id = kb_id
    
    def run_evaluation(
        self,
        retrieval_cases: List[RetrievalTestCase],
        qa_cases: List[QATestCase],
        output_dir: str = "./eval_results"
    ) -> Dict:
        """运行完整评估"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 检索评估
        print("评估检索质量...")
        retrieval_metrics = evaluate_retrieval(
            self.kb_id,
            retrieval_cases
        )
        
        # 生成评估
        print("评估生成质量...")
        generation_metrics = evaluate_rag_pipeline(
            self.kb_id,
            qa_cases
        )
        
        # 综合报告
        report = {
            "timestamp": timestamp,
            "kb_id": self.kb_id,
            "retrieval": retrieval_metrics,
            "generation": generation_metrics,
            "overall_score": self._calculate_overall_score(
                retrieval_metrics,
                generation_metrics
            )
        }
        
        # 保存结果
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        with open(output_path / f"eval_{timestamp}.json", "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report
    
    def _calculate_overall_score(
        self,
        retrieval: Dict,
        generation: Dict
    ) -> float:
        """计算综合分数"""
        
        # 加权平均
        retrieval_score = (
            retrieval["avg_recall"] * 0.3 +
            retrieval["avg_mrr"] * 0.3 +
            retrieval["hit_rate"] * 0.4
        )
        
        generation_score = generation["overall"] / 5  # 归一化到 0-1
        
        return retrieval_score * 0.4 + generation_score * 0.6

# 使用
evaluator = RAGEvaluator(client, openai, kb_id)
report = evaluator.run_evaluation(retrieval_cases, qa_cases)

print(f"\n=== 评估报告 ===")
print(f"检索召回率: {report['retrieval']['avg_recall']:.2%}")
print(f"检索 MRR: {report['retrieval']['avg_mrr']:.3f}")
print(f"生成质量: {report['generation']['overall']:.2f}/5")
print(f"综合得分: {report['overall_score']:.2%}")
```

## 持续优化策略

### A/B 测试框架

```python
import random

class ABTestManager:
    """A/B 测试管理器"""
    
    def __init__(self, variants: Dict[str, str]):
        """
        variants: {"A": kb_id_a, "B": kb_id_b}
        """
        self.variants = variants
        self.results = {v: [] for v in variants}
    
    def get_variant(self, user_id: str) -> str:
        """根据用户 ID 分配变体"""
        # 确定性分配
        hash_val = hash(user_id) % 100
        return "A" if hash_val < 50 else "B"
    
    def search(self, user_id: str, query: str, **kwargs):
        """执行搜索（自动选择变体）"""
        variant = self.get_variant(user_id)
        kb_id = self.variants[variant]
        
        results = client.knowledge_bases.search(
            kb_id=kb_id,
            query=query,
            **kwargs
        )
        
        return results, variant
    
    def record_feedback(self, variant: str, query: str, helpful: bool):
        """记录用户反馈"""
        self.results[variant].append({
            "query": query,
            "helpful": helpful
        })
    
    def get_statistics(self) -> Dict:
        """获取 A/B 测试统计"""
        stats = {}
        
        for variant, feedbacks in self.results.items():
            if feedbacks:
                helpful_count = sum(1 for f in feedbacks if f["helpful"])
                stats[variant] = {
                    "total": len(feedbacks),
                    "helpful": helpful_count,
                    "helpful_rate": helpful_count / len(feedbacks)
                }
        
        return stats

# 使用
ab_test = ABTestManager({
    "A": "kb_chunking_256",
    "B": "kb_chunking_512"
})

# 用户搜索
results, variant = ab_test.search("user_123", "年假政策")

# 记录反馈
ab_test.record_feedback(variant, "年假政策", helpful=True)

# 查看结果
print(ab_test.get_statistics())
```

### 反馈收集与分析

```python
from collections import defaultdict

class FeedbackCollector:
    """反馈收集器"""
    
    def __init__(self):
        self.feedbacks = defaultdict(list)
    
    def collect(
        self,
        query: str,
        retrieved_chunks: List,
        answer: str,
        user_rating: int,  # 1-5
        user_comment: str = ""
    ):
        """收集反馈"""
        self.feedbacks[query].append({
            "chunks": [c.id for c in retrieved_chunks],
            "answer": answer,
            "rating": user_rating,
            "comment": user_comment
        })
    
    def analyze(self) -> Dict:
        """分析反馈数据"""
        
        all_ratings = []
        low_rating_queries = []
        
        for query, feedbacks in self.feedbacks.items():
            ratings = [f["rating"] for f in feedbacks]
            avg_rating = sum(ratings) / len(ratings)
            all_ratings.extend(ratings)
            
            if avg_rating < 3:
                low_rating_queries.append({
                    "query": query,
                    "avg_rating": avg_rating,
                    "count": len(feedbacks)
                })
        
        return {
            "overall_avg_rating": sum(all_ratings) / len(all_ratings),
            "total_feedbacks": len(all_ratings),
            "low_rating_queries": sorted(
                low_rating_queries,
                key=lambda x: x["avg_rating"]
            )[:10]  # 前 10 个低分查询
        }

# 使用
collector = FeedbackCollector()

# 收集反馈
collector.collect(
    query="年假政策",
    retrieved_chunks=results.chunks,
    answer=generated_answer,
    user_rating=4,
    user_comment="基本满意，但缺少具体天数"
)

# 分析
analysis = collector.analyze()
print(f"平均评分: {analysis['overall_avg_rating']:.2f}")
print(f"需要优化的查询: {analysis['low_rating_queries']}")
```

## 评估报告模板

```markdown
# RAG 系统评估报告

## 评估概述
- 评估日期: {timestamp}
- 知识库 ID: {kb_id}
- 测试用例数: {num_cases}

## 检索质量
| 指标 | 数值 | 目标 | 状态 |
|-----|------|------|------|
| 召回率 | {recall}% | >80% | ✓/✗ |
| 精确率 | {precision}% | >70% | ✓/✗ |
| MRR | {mrr} | >0.7 | ✓/✗ |
| 命中率 | {hit_rate}% | >90% | ✓/✗ |

## 生成质量
| 维度 | 评分 | 目标 | 状态 |
|-----|------|------|------|
| 相关性 | {relevance}/5 | >4.0 | ✓/✗ |
| 准确性 | {accuracy}/5 | >4.0 | ✓/✗ |
| 完整性 | {completeness}/5 | >3.5 | ✓/✗ |

## 优化建议
1. {recommendation_1}
2. {recommendation_2}
3. {recommendation_3}
```

## 下一步

- [分块策略详解](../intermediate/chunking-strategies.md) - 优化检索效果
- [性能调优](performance-tuning.md) - 提升响应速度
- [LangChain 集成](../../integrations/langchain.md) - 框架集成
