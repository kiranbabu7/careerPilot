"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Loader2 } from "lucide-react";

import { AgentActivityCard } from "@/components/agents/agent-activity-card";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { agentsApi, type AgentExecution } from "@/lib/api";

export default function WorkspacePage() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<
    Array<{ role: "user" | "assistant"; content: string }>
  >([]);
  const [agentExecutions, setAgentExecutions] = useState<AgentExecution[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);

  const loadAgents = useCallback(async () => {
    setAgentsLoading(true);
    try {
      const data = await agentsApi.listExecutions();
      setAgentExecutions(data);
    } catch {
      setAgentExecutions([]);
    } finally {
      setAgentsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  const handleSend = () => {
    if (!message.trim()) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: message.trim() },
      {
        role: "assistant",
        content:
          "Workspace chat is a shell for now. Start a goal from Home to run Planner and Job Search agents.",
      },
    ]);
    setMessage("");
  };

  const latestByAgent = agentExecutions.reduce<Record<string, AgentExecution>>(
    (acc, execution) => {
      if (!acc[execution.agent_name]) {
        acc[execution.agent_name] = execution;
      }
      return acc;
    },
    {},
  );

  const displayAgents = ["planner", "job_search"]
    .map((name) => latestByAgent[name])
    .filter(Boolean) as AgentExecution[];

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="flex h-screen">
          <section className="flex flex-1 flex-col border-r border-border">
            <div className="border-b border-border px-6 py-4">
              <h1 className="text-lg font-semibold">Workspace</h1>
              <p className="text-sm text-muted-foreground">
                Collaborate with CareerPilot agents on your career goals
              </p>
            </div>

            <ScrollArea className="flex-1 px-6 py-4">
              {messages.length === 0 ? (
                <div className="flex h-full min-h-[320px] flex-col items-center justify-center text-center">
                  <Bot className="mb-4 h-10 w-10 text-muted-foreground" />
                  <p className="text-sm font-medium">No conversation yet</p>
                  <p className="mt-1 max-w-md text-sm text-muted-foreground">
                    Start by describing what you want to accomplish. Agents will
                    appear in the activity panel as workflows run.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((msg, index) => (
                    <div
                      key={`${msg.role}-${index}`}
                      className={
                        msg.role === "user"
                          ? "ml-auto max-w-[80%] rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground"
                          : "max-w-[80%] rounded-lg bg-muted px-4 py-3 text-sm"
                      }
                    >
                      {msg.content}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>

            <div className="border-t border-border p-4">
              <div className="flex gap-2">
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Describe your goal or ask a question..."
                  className="min-h-[80px] flex-1 resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <Button onClick={handleSend} disabled={!message.trim()}>
                  Send
                </Button>
              </div>
            </div>
          </section>

          <aside className="flex w-[360px] flex-col bg-muted/20">
            <div className="border-b border-border px-5 py-4">
              <h2 className="font-semibold">Agent activity</h2>
              <p className="text-xs text-muted-foreground">
                Latest Planner and Job Search runs
              </p>
            </div>

            <ScrollArea className="flex-1 px-5 py-4">
              {agentsLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading agent activity...
                </div>
              ) : displayAgents.length > 0 ? (
                <div className="space-y-3">
                  {displayAgents.map((execution) => (
                    <AgentActivityCard key={execution.id} execution={execution} />
                  ))}
                </div>
              ) : (
                <div className="space-y-3">
                  {["Planner", "Job Search"].map((name) => (
                    <Card key={name} className="bg-card/80">
                      <CardHeader className="p-4 pb-2">
                        <CardTitle className="flex items-center justify-between text-sm">
                          {name}
                          <span className="flex items-center gap-1 text-xs font-normal text-muted-foreground">
                            idle
                          </span>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-4 pt-0 text-xs text-muted-foreground">
                        Waiting for a workflow run.
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              <Separator className="my-4" />

              <div className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
                No active runs. Start a goal from{" "}
                <Link href="/" className="text-primary underline-offset-4 hover:underline">
                  Home
                </Link>{" "}
                to begin.
              </div>
            </ScrollArea>
          </aside>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
