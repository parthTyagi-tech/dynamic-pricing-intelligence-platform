import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, Brain, MessageSquare, Bot, HelpCircle, ShieldCheck, RefreshCw, Table } from "lucide-react";
import apiClient from "../services/api";
import { useAuth } from "../context/AuthContext";

// Simple custom component to parse basic Markdown formatting (bold, headers, bullets, inline code, links, tables)
function MessageFormatter({ content }) {
  if (!content) return null;

  // Split content by lines
  const lines = content.split("\n");
  const parsedElements = [];
  let currentTable = null;

  const parseInline = (text) => {
    // Bold: **text**
    let parts = [text];
    const boldRegex = /\*\*(.*?)\*\*/g;
    let match;
    
    // Simple inline parser for bold and code
    // Replaces markdown formatting with React nodes
    const formatBoldAndCode = (str) => {
      const boldParts = str.split(/\*\*(.*?)\*\*/g);
      return boldParts.map((bPart, idx) => {
        if (idx % 2 === 1) {
          return <strong key={`bold-${idx}`} className="text-white font-bold">{bPart}</strong>;
        }
        
        // Code: `code`
        const codeParts = bPart.split(/`(.*?)`/g);
        return codeParts.map((cPart, cIdx) => {
          if (cIdx % 2 === 1) {
            return (
              <code key={`code-${cIdx}`} className="bg-white/10 text-teal-300 font-mono text-xs px-1.5 py-0.5 rounded border border-white/5">
                {cPart}
              </code>
            );
          }
          
          // Links: [text](url)
          const linkParts = cPart.split(/\[(.*?)\]\((.*?)\)/g);
          if (linkParts.length > 1) {
            return linkParts.map((lPart, lIdx) => {
              if (lIdx % 3 === 1) {
                const label = lPart;
                const url = linkParts[lIdx + 1];
                return (
                  <a
                    key={`link-${lIdx}`}
                    href={url}
                    className="text-[#059669] hover:text-[#10b981] hover:underline font-semibold transition-all inline-flex items-center gap-1"
                  >
                    {label}
                  </a>
                );
              } else if (lIdx % 3 === 2) {
                return null; // Skip URL part
              }
              return lPart;
            });
          }
          
          return cPart;
        });
      });
    };

    return formatBoldAndCode(text);
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // 1. Table handling
    if (line.startsWith("|")) {
      const cells = line.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      
      // If it's a separator line like |---|---|
      if (line.includes("---")) {
        continue;
      }

      if (!currentTable) {
        currentTable = { headers: cells, rows: [] };
      } else {
        currentTable.rows.push(cells);
      }
      continue;
    } else if (currentTable) {
      // Table ended, push table element
      const table = currentTable;
      parsedElements.push(
        <div key={`table-${i}`} className="my-4 overflow-x-auto rounded-xl border border-white/10 bg-white/5 backdrop-blur-md">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/10">
              <tr>
                {table.headers.map((h, hIdx) => (
                  <th key={hIdx} className="px-4 py-3 text-left font-semibold text-white tracking-wider">
                    {parseInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {table.rows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-white/5 transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-4 py-2.5 text-slate-300">
                      {parseInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      currentTable = null;
    }

    // 2. Headers handling
    if (line.startsWith("###")) {
      parsedElements.push(
        <h3 key={i} className="text-lg font-bold text-white mt-4 mb-2 flex items-center gap-2">
          {parseInline(line.substring(3).trim())}
        </h3>
      );
    } else if (line.startsWith("####")) {
      parsedElements.push(
        <h4 key={i} className="text-base font-semibold text-white mt-3 mb-1">
          {parseInline(line.substring(4).trim())}
        </h4>
      );
    } 
    // 3. Bullets handling
    else if (line.startsWith("-") || line.startsWith("*")) {
      parsedElements.push(
        <li key={i} className="ml-5 list-disc text-sm text-slate-300 leading-relaxed py-0.5">
          {parseInline(line.substring(1).trim())}
        </li>
      );
    }
    // 4. Blank lines
    else if (line === "") {
      parsedElements.push(<div key={i} className="h-2" />);
    }
    // 5. Plain paragraphs
    else {
      parsedElements.push(
        <p key={i} className="text-sm text-slate-300 leading-relaxed my-1">
          {parseInline(line)}
        </p>
      );
    }
  }

  // If table remains at the end
  if (currentTable) {
    const table = currentTable;
    parsedElements.push(
      <div key="table-end" className="my-4 overflow-x-auto rounded-xl border border-white/10 bg-white/5 backdrop-blur-md">
        <table className="min-w-full divide-y divide-white/10 text-sm">
          <thead className="bg-white/10">
            <tr>
              {table.headers.map((h, hIdx) => (
                <th key={hIdx} className="px-4 py-3 text-left font-semibold text-white tracking-wider">
                  {parseInline(h)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {table.rows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-white/5 transition-colors">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="px-4 py-2.5 text-slate-300">
                    {parseInline(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return <div className="space-y-1">{parsedElements}</div>;
}

export default function Chat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([
    {
      sender: "ai",
      text: `Hello ${user?.name || "there"}! I am **Klypup AI**, your pricing coordinator and the orchestrator of all specialized agents (Market, Demand, Inventory, Strategy, and Compliance). 

I can execute command queries or launch real-time dynamic pricing analysis loops for products.

Try asking me:
- "analyse Premium Wireless Headphones"
- "price of Ergonomic Office Chair"
- "list products"
- "list recommendations"
- "help"`
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const quickActions = [
    { label: "Help Guide", command: "help", icon: HelpCircle },
    { label: "Catalog Summary", command: "list products", icon: Table },
    { label: "Analyse Headphones", command: "analyse Premium Wireless Headphones", icon: Brain },
    { label: "Show Pending Approvals", command: "list recommendations", icon: RefreshCw },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSendMessage = async (textToSend) => {
    const text = (textToSend || input).trim();
    if (!text) return;

    if (!textToSend) {
      setInput("");
    }

    // Add user message
    setMessages((prev) => [...prev, { sender: "user", text }]);
    setLoading(true);

    try {
      // Map history format: { role: "user" | "assistant", content: string }
      const historyFormatted = messages.map((m) => ({
        role: m.sender === "user" ? "user" : "assistant",
        content: m.text,
      }));

      const response = await apiClient.post("/chatbot/chat", {
        message: text,
        history: historyFormatted,
      });

      setMessages((prev) => [
        ...prev,
        { sender: "ai", text: response.data.response || "No response received." },
      ]);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: "⚠️ Sorry, I encountered an error communicating with the coordinator backend. Make sure the Flask server is running."
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-130px)]">
      {/* HEADER SECTION */}
      <div className="relative overflow-hidden rounded-[24px] border border-white/10 p-6 mb-6"
           style={{ background: "linear-gradient(135deg,rgba(8,8,8,0.72),rgba(0,0,0,0.85))", boxShadow: "0 20px 50px rgba(0,0,0,0.3)" }}>
        <div className="absolute top-0 right-0 w-24 h-24 opacity-15 blur-2xl bg-gradient-to-br from-[#059669] to-indigo-500" />
        <div className="relative z-10 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-gradient-to-br from-[#059669] to-indigo-500">
            <Bot className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              Klypup AI Copilot
              <span className="text-xs bg-[#059669]/20 text-[#ffffff] px-2 py-0.5 rounded-full border border-[#059669]/20 font-semibold tracking-wider">
                SUPERVISOR MODE
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Ask questions or command agents to run real-time pricing strategy loops.
            </p>
          </div>
        </div>
      </div>

      {/* CHAT MESSAGES WINDOW */}
      <div className="flex-1 overflow-y-auto glass-card rounded-[24px] p-6 mb-4 flex flex-col gap-4 border border-white/8">
        <div className="flex-1 flex flex-col gap-4">
          {messages.map((msg, index) => (
            <div key={index} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`flex gap-3 max-w-[85%] ${msg.sender === "user" ? "flex-row-reverse" : "flex-row"}`}>
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-1 shadow ${
                  msg.sender === "user" ? "bg-indigo-600" : "bg-teal-700"
                }`}>
                  {msg.sender === "user" ? <MessageSquare size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
                </div>
                
                <div className={`rounded-2xl p-4 shadow-md border ${
                  msg.sender === "user"
                    ? "bg-indigo-600/30 border-indigo-500/30 text-white rounded-tr-none"
                    : "bg-white/5 border-white/10 rounded-tl-none"
                }`}>
                  <MessageFormatter content={msg.text} />
                </div>
              </div>
            </div>
          ))}

          {/* Typing Indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="flex gap-3 max-w-[80%]">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-teal-700 shadow">
                  <Bot size={14} className="text-white" />
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-none p-4 flex items-center gap-1.5 h-11">
                  <div className="w-2 h-2 bg-[#059669] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-[#059669] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 bg-[#059669] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* QUICK ACTIONS ROW */}
      <div className="flex gap-2.5 overflow-x-auto pb-3 scrollbar-none flex-wrap">
        {quickActions.map((act, idx) => (
          <button
            key={idx}
            disabled={loading}
            onClick={() => handleSendMessage(act.command)}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-slate-300 bg-white/5 hover:bg-white/10 border border-white/8 hover:border-white/15 rounded-full transition-all cursor-pointer select-none"
          >
            <act.icon size={12} className="text-[#059669]" />
            {act.label}
          </button>
        ))}
      </div>

      {/* INPUT BAR */}
      <div className="flex gap-3 items-center">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyPress}
          disabled={loading}
          placeholder="Ask a question or type 'analyse [product SKU]'..."
          className="flex-1 bg-white/5 border border-white/10 text-white rounded-xl px-4 py-3.5 text-sm outline-none focus:border-[#059669]/50 transition-all placeholder:text-slate-500"
        />
        <button
          onClick={() => handleSendMessage()}
          disabled={loading || !input.trim()}
          className="w-12 h-12 rounded-xl flex items-center justify-center bg-gradient-to-br from-[#059669] to-indigo-600 hover:from-[#10b981] hover:to-indigo-500 transition-all shadow-lg shadow-indigo-650/20 text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
