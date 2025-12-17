import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { motion } from "framer-motion";
import { Bot, BrainCircuit, Send, Sparkles, User, Loader2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import ReactMarkdown from 'react-markdown';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
}

export default function Innovation() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Create a placeholder assistant message
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: "",
      timestamp: new Date(),
      isLoading: true
    }]);

    // Simulate Phase 1 Chat Response
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    const responseContent = `**Phase 1 Analysis:**\n\nI've analyzed your request regarding "${userMessage.content}". \n\nTo optimize your DevOps workflow, I recommend focusing on:\n1. **Automated Testing:** Integrate unit and integration tests into your CI pipeline.\n2. **Infrastructure as Code:** Use Terraform or Ansible to manage your infrastructure.\n3. **Monitoring & Logging:** Implement robust monitoring with Prometheus and Grafana.\n\nThis aligns with the Council's strategic direction for scalable and resilient systems.`;

    setMessages(prev => prev.map((msg, idx) => 
      idx === prev.length - 1 ? { ...msg, isLoading: false, content: responseContent } : msg
    ));

    setIsLoading(false);
  };

  return (
    <Layout>
      <div className="flex flex-col min-h-[calc(100vh-80px)] relative">
        {/* Background Image with Overlay */}
        <div className="absolute inset-0 z-0">
          <img 
            src="/images/innovation-council-v2.png" 
            alt="Council Background" 
            className="w-full h-full object-cover opacity-60"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-background/80 via-background/60 to-background/90" />
        </div>

        {/* Header */}
        <div className="bg-background/80 backdrop-blur-md border-b border-white/10 p-4 z-10 relative">
          <div className="container mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10 text-primary">
                <BrainCircuit size={24} />
              </div>
              <div>
                <h1 className="text-xl font-display font-bold">DevOps AI Council</h1>
                <p className="text-xs text-muted-foreground">Phase 1: Strategic Consultation</p>
              </div>
            </div>
            <div className="hidden md:flex items-center gap-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-green-500"></div> Online</span>
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 p-4 md:p-8 relative z-10 pb-24">
          <div className="container mx-auto max-w-4xl space-y-8">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-6">
                <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center animate-pulse">
                  <Sparkles size={48} className="text-primary" />
                </div>
                <div>
                  <h2 className="text-3xl font-display font-bold mb-2">How can the Council assist you?</h2>
                  <p className="text-muted-foreground max-w-md mx-auto">
                    Submit a business challenge or technical query. Our council of AI models will deliberate to inform your DevOps workflow.
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-2xl">
                  {[
                    "How can AI improve our CI/CD pipeline?",
                    "Best practices for microservices security.",
                    "Strategies for reducing cloud costs.",
                    "Implementing GitOps for Kubernetes."
                  ].map((suggestion, i) => (
                    <button 
                      key={i}
                      onClick={() => setInput(suggestion)}
                      className="p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 hover:border-primary/30 transition-all text-left text-sm"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, index) => (
                <motion.div 
                  key={index}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 border border-primary/30">
                      <Bot size={20} className="text-primary" />
                    </div>
                  )}
                  
                  <div className={`max-w-[85%] md:max-w-[75%] space-y-4`}>
                    <div className={`p-4 rounded-2xl ${
                      msg.role === 'user' 
                        ? 'bg-primary text-primary-foreground rounded-tr-none' 
                        : 'glass-panel border border-white/10 rounded-tl-none'
                    }`}>
                      {msg.isLoading ? (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Loader2 size={16} className="animate-spin" />
                          <span>Consulting the Council...</span>
                        </div>
                      ) : (
                        <div className="prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground px-2">
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>

                  {msg.role === 'user' && (
                    <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center flex-shrink-0 border border-white/20">
                      <User size={20} />
                    </div>
                  )}
                </motion.div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="fixed bottom-0 left-0 right-0 bg-background/80 backdrop-blur-md border-t border-white/10 p-4 z-20">
          <div className="container mx-auto max-w-4xl">
            <form onSubmit={handleSendMessage} className="relative">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Consult the Council..."
                className="pr-12 h-14 rounded-2xl bg-white/5 border-white/10 focus:border-primary/50 text-lg shadow-lg"
                disabled={isLoading}
              />
              <Button 
                type="submit" 
                size="icon"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 top-2 h-10 w-10 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground transition-all"
              >
                {isLoading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
              </Button>
            </form>
            <p className="text-center text-xs text-muted-foreground mt-3">
              Phase 1: Initial Strategic Consultation. Future phases will include multi-model deliberation.
            </p>
          </div>
        </div>
      </div>
    </Layout>
  );
}
