# from typing import TypedDict

# from langgraph.graph import StateGraph, START, END


# class GraphState(TypedDict):
#     message: str


# def node_a(state: GraphState):
#     print("Node A executed")
#     return state


# def node_b(state: GraphState):
#     print("Node B executed")
#     return state


# builder = StateGraph(GraphState)

# builder.add_node("node_a", node_a)
# builder.add_node("node_b", node_b)

# builder.add_edge(START, "node_a")
# builder.add_edge("node_a", "node_b")
# builder.add_edge("node_b", END)

# graph = builder.compile()