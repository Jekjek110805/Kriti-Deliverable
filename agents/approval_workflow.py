class ApprovalWorkflowAgent:
    def run(self, report):
        approval_queue = []

        for item in report:
            approval_queue.append({
                "topic": item.get("topic"),
                "keyword": item.get("keyword"),
                "recommendation": item.get("recommendation"),
                "priority": item.get("priority"),
                "reviewer": "TBD",
                "status": item.get("approval_status", "Pending Human Approval"),
                "approval_options": [
                    "Approved",
                    "Approved with Notes",
                    "Rejected",
                    "Needs Further Research"
                ]
            })

        return approval_queue
