'use client';

import { useState } from 'react';
import { Send, Loader2, CheckCircle, AlertCircle, FileText, Bot, Zap, Shield, Brain } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  mathResult?: any;
  practiceNotes?: any[];
  olderSources?: any[];
  verifierResult?: any;
  status?: string;
  executionLane?: string;
}

interface Citation {
  block_id: string;
  source: string;
  section: string;
  valid_from: string;
  quote: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Welcome to **Meridian Knowledge Engine** — a Generic Dual-Clock Temporal Knowledge Engine with Industry Plug-ins.

**Meridian AP** is the first plug-in, solving Accounts Payable for Meridian Shared Services.

**Try asking:**
- "What is the price tolerance limit?"
- "PO price ₹395, invoice ₹400 for 500 bags. Pass or variance?"
- "TDS on software support, taxable value ₹4,80,000 plus GST?"
- "Micro supplier accepted 1 Aug 2026, no agreement. Due date?"
- "Pharma excipient invoices need QA release before payment?"
- "Infra invoice received Saturday with no GRN. Chase Monday?"`,
      status: 'READY',
      executionLane: 'SYSTEM',
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/v1';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    const query = input;
    setInput('');

    try {
      const response = await fetch(`${API_URL}/query/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-Slug': 'meridian',
        },
        body: JSON.stringify({
          query_text: query,
          client_desk: 'ALL',
          as_of_date: '2026-08-01',
        }),
      });

      const data = await response.json();
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer_markdown || 'No answer returned',
        citations: data.citations,
        mathResult: data.math_result,
        practiceNotes: data.practice_notes,
        olderSources: data.older_sources,
        verifierResult: data.verifier_result,
        status: data.status,
        executionLane: data.execution_lane,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Failed to query engine'}`,
        status: 'ERROR',
        executionLane: 'ERROR',
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 font-sans">
      {/* Header */}
      <header className="border-b border-neutral-200 bg-white sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary-600 flex items-center justify-center">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="font-display text-xl font-bold text-neutral-900">Meridian Knowledge Engine</h1>
                <p className="text-xs text-neutral-500">Generic Dual-Clock Temporal Knowledge Engine</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-sm text-neutral-500">
              <span className="px-2 py-1 rounded bg-primary-50 text-primary-700">Meridian AP Plug-in</span>
              <span className="px-2 py-1 rounded bg-neutral-100 text-neutral-600">v0.1.0</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1">
        <div className="space-y-6">
          {/* Messages */}
          <div className="space-y-4" id="messages">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && (
              <div className="flex items-center gap-2 text-neutral-500">
                <Loader2 className="w-5 h-5 animate-spin text-primary-600" />
                <span>Thinking...</span>
              </div>
            )}
          </div>

          {/* Input Form */}
          <form onSubmit={handleSubmit} className="fixed bottom-0 left-0 right-0 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
            <div className="bg-white border-t border-neutral-200 p-4">
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask about price tolerance, TDS, MSME, e-invoice, GRN, or any AP exception..."
                    rows={1}
                    className="input resize-none min-h-[44px] max-h-48"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit(e);
                      }
                    }}
                    disabled={isLoading}
                  />
                </div>
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className="btn-primary h-10 px-6"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4 mr-2" />
                      Send
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      </main>

      {/* Footer Stats */}
      <footer className="border-t border-neutral-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center text-sm text-neutral-500">
            <div>
              <div className="font-bold text-primary-600">T1-T10</div>
              <div>Acceptance Tests</div>
            </div>
            <div>
              <div className="font-bold text-primary-600">160 Qs</div>
              <div>Gold Evaluation Set</div>
            </div>
            <div>
              <div className="font-bold text-primary-600">Ragas</div>
              <div>Faithfulness ≥0.95</div>
            </div>
            <div>
              <div className="font-bold text-primary-600">Generality</div>
              <div>2nd Company Test</div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  const statusColors = {
    PASS: 'badge-success',
    PRICE_VAR: 'badge-warning',
    IRN_MISSING: 'badge-error',
    TDS_SECTION_UNCLEAR: 'badge-warning',
    ABSTAIN: 'badge-info',
    ESCALATED: 'badge-error',
    REFUSED: 'badge-info',
    SUCCESS: 'badge-success',
    ERROR: 'badge-error',
    SYSTEM: 'badge-info',
    READY: 'badge-info',
  };

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
          <Brain className="w-5 h-5 text-primary-600" />
        </div>
      )}
      <div className={`flex-1 ${isUser ? 'text-right' : ''}`}>
        <div className={`card-base p-4 ${isUser ? 'bg-primary-50 border-primary-200' : ''}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">
              {isUser ? 'You' : 'Meridian Engine'}
            </span>
            <div className="flex items-center gap-2">
              {message.executionLane && (
                <span className={`badge ${statusColors[message.executionLane as keyof typeof statusColors] || 'badge-info'}`}>
                  {message.executionLane}
                </span>
              )}
              {message.status && message.status !== message.executionLane && (
                <span className={`badge ${statusColors[message.status as keyof typeof statusColors] || 'badge-info'}`}>
                  {message.status}
                </span>
              )}
            </div>
          </div>
          <div className="prose prose-sm max-w-none text-neutral-800">
            {message.content.split('\n').map((line, i) => (
              <p key={i} className="whitespace-pre-wrap">{line}</p>
            ))}
          </div>

          {/* Math Result */}
          {message.mathResult && (
            <div className="mt-3 p-3 bg-neutral-50 rounded-lg border border-neutral-200">
              <h4 className="font-medium text-sm text-neutral-700 mb-2">Calculation Details</h4>
              <pre className="text-xs bg-white p-2 rounded border border-neutral-200 overflow-x-auto">
                {JSON.stringify(message.mathResult, null, 2)}
              </pre>
            </div>
          )}

          {/* Citations */}
          {message.citations && message.citations.length > 0 && (
            <div className="mt-3">
              <h4 className="font-medium text-sm text-neutral-700 mb-2">Citations</h4>
              <div className="space-y-2">
                {message.citations.map((c: any, i: number) => (
                  <div key={i} className="p-3 bg-white border border-neutral-200 rounded-lg">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-medium text-neutral-700">{c.source}</span>
                      <span className="text-neutral-500">{c.section}</span>
                    </div>
                    <p className="text-sm text-neutral-600 italic">"{c.quote}"</p>
                    <p className="text-xs text-neutral-400 mt-1">Valid from: {c.valid_from}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Practice Notes (Side-by-Side) */}
          {message.practiceNotes && message.practiceNotes.length > 0 && (
            <div className="mt-3">
              <h4 className="font-medium text-sm text-neutral-700 mb-2 flex items-center gap-2">
                <Zap className="w-4 h-4 text-warning-600" />
                Expert Practice (Side-by-Side)
              </h4>
              <div className="space-y-2">
                {message.practiceNotes.map((p: any, i: number) => (
                  <div key={i} className="p-3 bg-warning-50 border border-warning-200 rounded-lg">
                    <p className="text-sm text-warning-800">{p.habit_description || p.action_to_take || JSON.stringify(p)}</p>
                    <p className="text-xs text-warning-600 mt-1">Source: {p.source_timestamp || 'Expert Interview'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Older Sources */}
          {message.olderSources && message.olderSources.length > 0 && (
            <div className="mt-3">
              <h4 className="font-medium text-sm text-neutral-700 mb-2 flex items-center gap-2">
                <FileText className="w-4 h-4 text-neutral-500" />
                Superseded / Older Sources
              </h4>
              <div className="space-y-2">
                {message.olderSources.map((s: any, i: number) => (
                  <div key={i} className="p-3 bg-neutral-50 border border-neutral-200 rounded-lg">
                    <p className="text-sm text-neutral-600">{s.note || s.source}</p>
                    <p className="text-xs text-neutral-400 mt-1">Valid: {s.valid_from} → {s.valid_to || 'present'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Verifier Result */}
          {message.verifierResult && (
            <div className="mt-3 p-3 rounded-lg border"
              className={message.verifierResult.passed ? 'bg-success-50 border-success-200' : 'bg-error-50 border-error-200'}>
              <div className="flex items-center gap-2 text-sm">
                {message.verifierResult.passed ? (
                  <CheckCircle className="w-4 h-4 text-success-600" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-error-600" />
                )}
                <span className="font-medium">
                  {message.verifierResult.passed ? 'Verified ✓' : 'Verification Failed'}
                </span>
              </div>
              <div className="mt-2 text-xs text-neutral-600 grid grid-cols-2 gap-1">
                {Object.entries(message.verifierResult.checks || {}).map(([check, passed]) => (
                  <div key={check} className={passed ? 'text-success-600' : 'text-error-600'}>
                    {passed ? '✓' : '✗'} {check.replace(/_/g, ' ')}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-neutral-200 flex items-center justify-center flex-shrink-0">
          <span className="text-sm font-medium text-neutral-600">You</span>
        </div>
      )}
    </div>
  );
}