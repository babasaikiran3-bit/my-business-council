import Layout from "@/components/Layout";
import { motion } from "framer-motion";
import { Code2, Database, Server, Layers } from "lucide-react";

export default function Technology() {
  const techStack = [
    {
      category: "Frontend & UI",
      icon: <Layers size={24} />,
      items: ["React", "TypeScript", "TailwindCSS", "Framer Motion", "Vite", "Radix UI"]
    },
    {
      category: "Backend & API",
      icon: <Server size={24} />,
      items: ["FastAPI (Python)", "Node.js", "Supabase", "PostgreSQL", "REST & GraphQL"]
    },
    {
      category: "AI & ML",
      icon: <Code2 size={24} />,
      items: ["OpenAI", "AWS Bedrock", "Anthropic Claude", "xAI Grok", "LangChain", "Vector Databases"]
    },
    {
      category: "Automation & Ops",
      icon: <Database size={24} />,
      items: ["n8n", "Docker", "Linux (Ubuntu)", "GitHub Actions", "AWS / Azure"]
    }
  ];

  return (
    <Layout>
      <section className="pt-32 pb-16">
        <div className="container px-4 text-center">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-5xl md:text-7xl font-display font-bold mb-6"
          >
            Our <span className="text-gradient-accent">Tech Stack</span>
          </motion.h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            We build on solid foundations. Our technology choices prioritize scalability, maintainability, and performance.
          </p>
        </div>
      </section>

      {/* Tech Grid */}
      <section className="py-16">
        <div className="container px-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {techStack.map((stack, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="glass-panel p-8 rounded-3xl"
              >
                <div className="flex items-center gap-4 mb-6">
                  <div className="p-3 rounded-xl bg-primary/20 text-primary">
                    {stack.icon}
                  </div>
                  <h3 className="text-2xl font-bold">{stack.category}</h3>
                </div>
                <div className="flex flex-wrap gap-3">
                  {stack.items.map((item, i) => (
                    <span 
                      key={i}
                      className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm font-medium hover:bg-white/10 transition-colors"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Project Highlights (Inspired by GitHub) */}
      <section className="py-24 bg-white/5">
        <div className="container px-4">
          <h2 className="text-3xl md:text-4xl font-display font-bold mb-12 text-center">Innovation in Action</h2>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
            {/* Project 1: LLM Council */}
            <div className="glass-panel p-8 rounded-3xl border-l-4 border-l-primary">
              <div className="mb-4 text-xs font-mono text-primary uppercase tracking-widest">Experimental</div>
              <h3 className="text-2xl font-bold mb-4">LLM Council</h3>
              <p className="text-muted-foreground mb-6">
                A collaborative AI decision-making framework where multiple Large Language Models (OpenAI, Claude, AWS Bedrock, Grok) debate and rank each other's responses to produce a superior consensus answer.
              </p>
              <div className="flex gap-4 text-sm text-muted-foreground font-mono">
                <span>Python</span>
                <span>FastAPI</span>
                <span>React</span>
              </div>
            </div>

            {/* Project 2: NytroAI */}
            <div className="glass-panel p-8 rounded-3xl border-l-4 border-l-purple-500">
              <div className="mb-4 text-xs font-mono text-purple-400 uppercase tracking-widest">Production</div>
              <div className="flex items-center gap-3 mb-4">
                <img src="/images/nytro-logo.webp" alt="Nytro Logo" className="h-8 w-auto" />
              </div>
              <p className="text-muted-foreground mb-6">
                An advanced RTO assessment validation system using AWS Bedrock. Features real-time progress tracking, individual requirement validation for maximum accuracy, and automated citation generation.
              </p>
              <div className="flex gap-4 text-sm text-muted-foreground font-mono">
                <span>Supabase</span>
                <span>n8n</span>
                <span>AWS Bedrock</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </Layout>
  );
}
