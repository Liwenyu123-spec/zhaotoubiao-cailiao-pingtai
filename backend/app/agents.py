"""阶段 2 Agent 编排骨架。

当前节点只使用本地规则，不调用模型；后续可在同一节点中替换为 LangChain
Retriever/LLM，LangGraph 负责保留状态和人工确认边界。
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class TaskPlanState(TypedDict, total=False):
    requirements: list[dict]
    suggestions: list[dict]
    trace: list[str]
    needs_human_review: bool


def load_requirements(state: TaskPlanState) -> TaskPlanState:
    return {"trace": state.get("trace", []) + ["load_requirements"]}


def suggest_tasks(state: TaskPlanState) -> TaskPlanState:
    department_by_category = {
        "资格": "商务",
        "商务": "商务",
        "技术": "技术",
        "评分": "投标负责人",
        "格式": "投标负责人",
        "签章": "法务合规",
        "时间": "投标负责人",
    }
    suggestions = [
        {
            "requirement_id": item["id"],
            "department": department_by_category.get(item.get("category"), "投标负责人"),
            "reason": "按要求类别生成的任务建议，需人工确认后创建任务",
        }
        for item in state.get("requirements", [])
        if item.get("status") != "not_applicable"
    ]
    return {
        "suggestions": suggestions,
        "trace": state.get("trace", []) + ["suggest_tasks"],
        "needs_human_review": True,
    }


def human_review_gate(state: TaskPlanState) -> TaskPlanState:
    return {"trace": state.get("trace", []) + ["human_review_gate"]}


def build_task_plan_graph():
    graph = StateGraph(TaskPlanState)
    graph.add_node("load_requirements", load_requirements)
    graph.add_node("suggest_tasks", suggest_tasks)
    graph.add_node("human_review_gate", human_review_gate)
    graph.add_edge(START, "load_requirements")
    graph.add_edge("load_requirements", "suggest_tasks")
    graph.add_edge("suggest_tasks", "human_review_gate")
    graph.add_edge("human_review_gate", END)
    return graph.compile()


task_plan_graph = build_task_plan_graph()
