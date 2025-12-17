import Layout from "@/components/Layout";
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Bot, User, Sparkles, Terminal, Cpu, Shield, Zap, Users } from "lucide-react";
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function Innovation() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Greetings. I am the **DevOps AI Council** interface. \n\nI can assist you with:\n- **Strategic DevOps Roadmaps**\n- **Infrastructure Automation**\n- **Security & Compliance (DevSecOps)**\n- **AI-Driven Observability**\n\nHow can we accelerate your delivery today?",
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    // Simulate AI processing
    setTimeout(() => {
      const response: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: generateResponse(input),
        timestamp: new Date()
      };
      setMessages(prev => [...prev, response]);
      setIsTyping(false);
    }, 1500);
  };

  const generateResponse = (query: string): string => {
    const lowerQuery = query.toLowerCase();
    if (lowerQuery.includes("security") || lowerQuery.includes("compliance")) {
      return "### Security Council Deliberation\n\n**Consensus:** Shift security left.\n\n**Recommendation:**\n1. Implement **SAST/DAST** in your CI pipeline.\n2. Enforce **Policy-as-Code** using OPA (Open Policy Agent).\n3. Automate vulnerability scanning for all container images.\n\n*\"Security is not a gate, it's a continuous thread.\"*";
    }
    if (lowerQuery.includes("cloud") || lowerQuery.includes("aws") || lowerQuery.includes("azure")) {
      return "### Infrastructure Council Deliberation\n\n**Consensus:** Adopt immutable infrastructure.\n\n**Recommendation:**\n- Use **Terraform** or **Pulumi** for IaC.\n- Treat servers as cattle, not pets.\n- Implement auto-scaling groups based on custom metrics.\n\n*\"Consistency is the bedrock of reliability.\"*";
    }
    return "### Strategic Council Deliberation\n\n**Analysis:** Your query touches on core operational efficiency.\n\n**Recommendation:**\nTo provide a precise roadmap, we recommend a **Value Stream Mapping** session. However, as an immediate step, consider automating your manual handoffs using event-driven architecture.\n\nWould you like to explore **AI-driven incident response** next?";
  };

  return (
    <Layout>
      {/* Header Section - Standard Layout */}
      <section className="pt-32 pb-12 relative overflow-hidden">
        <div className="container px-4 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary mb-6 border border-primary/20"
          >
            <Sparkles size={16} />
            <span className="text-sm font-medium">Phase 1: Strategic Consultation</span>
          </motion.div>
          
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-4xl md:text-6xl font-display font-bold mb-6"
          >
            DevOps <span className="text-gradient-accent">AI Council</span>
          </motion.h1>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed"
          >
            Engage with our autonomous collective of specialized AI agents to solve complex infrastructure and operational challenges.
          </motion.p>
        </div>
      </section>

      {/* Main Content Area */}
      <section className="pb-24">
        <div className="container px-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 h-[800px]">
            
            {/* Left Column: Council Visuals & Info */}
            <div className="lg:col-span-1 flex flex-col gap-6">
              {/* Council Image Card */}
              <motion.div 
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 }}
                className="glass-panel p-2 rounded-2xl overflow-hidden h-64 relative group"
              >
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10" />
                <img 
                  src="/images/innovation-council-v2.png" 
                  alt="AI Council Chamber" 
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute bottom-4 left-4 z-20">
                  <h3 className="text-white font-bold text-lg flex items-center gap-2">
                    <Users size={18} className="text-primary" />
                    The Council
                  </h3>
                  <p className="text-white/70 text-sm">5 Active Agents</p>
                </div>
              </motion.div>

              {/* Capabilities List */}
              <motion.div 
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 }}
                className="glass-panel p-6 rounded-2xl flex-1 flex flex-col gap-4"
              >
                <h3 className="font-display font-bold text-xl mb-2">Active Modules</h3>
                
                {[
                  { icon: <Terminal size={20} />, label: "Infrastructure as Code", status: "Online" },
                  { icon: <Shield size={20} />, label: "Security Operations", status: "Active" },
                  { icon: <Cpu size={20} />, label: "Performance Tuning", status: "Standby" },
                  { icon: <Zap size={20} />, label: "CI/CD Automation", status: "Online" }
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                    <div className="flex items-center gap-3">
                      <div className="text-primary">{item.icon}</div>
                      <span className="font-medium text-sm">{item.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${item.status === 'Standby' ? 'bg-yellow-500' : 'bg-green-500 animate-pulse'}`} />
                      <span className="text-xs text-muted-foreground">{item.status}</span>
                    </div>
                  </div>
                ))}
              </motion.div>
            </div>

            {/* Right Column: Chat Interface */}
            <motion.div 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="lg:col-span-2 glass-panel rounded-2xl flex flex-col overflow-hidden border border-white/10 shadow-2xl"
            >
              {/* Chat Header */}
              <div className="p-4 border-b border-white/10 bg-black/20 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary">
                    <Bot size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm">Council Session #4291</h3>
                    <p className="text-xs text-muted-foreground">Secure Channel • Encrypted</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/20 border border-yellow-500/50" />
                  <div className="w-3 h-3 rounded-full bg-green-500/20 border border-green-500/50" />
                </div>
              </div>

              {/* Messages Area */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-black/20">
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      msg.role === 'user' ? 'bg-purple-500/20 text-purple-400' : 'bg-primary/20 text-primary'
                    }`}>
                      {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                    </div>
                    
                    <div className={`max-w-[80%] rounded-2xl p-4 ${
                      msg.role === 'user' 
                        ? 'bg-purple-500/10 border border-purple-500/20 text-purple-100' 
                        : 'bg-white/5 border border-white/10 text-gray-200'
                    }`}>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                      <span className="text-[10px] opacity-50 mt-2 block">
                        {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </motion.div>
                ))}
                {isTyping && (
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex gap-4"
                  >
                    <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 text-primary">
                      <Bot size={16} />
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex items-center gap-1">
                      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </motion.div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Area */}
              <div className="p-4 border-t border-white/10 bg-black/40">
                <div className="relative">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Ask the council about your DevOps strategy..."
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-4 pl-4 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all placeholder:text-muted-foreground/50"
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim()}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <Send size={18} />
                  </button>
                </div>
                <p className="text-center text-[10px] text-muted-foreground mt-3">
                  AI Council responses are simulated for Phase 1. Strategic advice should be verified by human experts.
                </p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>
    </Layout>
  );
}
