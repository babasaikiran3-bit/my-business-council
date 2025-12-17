import Layout from "@/components/Layout";
import { motion } from "framer-motion";
import { Cpu, Network, Workflow, CheckCircle2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "wouter";

export default function Services() {
  return (
    <Layout>
      <section className="pt-32 pb-16">
        <div className="container px-4 text-center">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-5xl md:text-7xl font-display font-bold mb-6"
          >
            Our <span className="text-gradient-accent">Services</span>
          </motion.h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            We deliver strategic business value through intelligent integration, automated efficiency, and AI-driven innovation.
          </p>
        </div>
      </section>

      {/* Service 1: AI */}
      <section className="py-24 relative">
        <div className="container px-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <motion.div 
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="order-2 lg:order-1"
            >
              <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mb-6 text-primary">
                <Cpu size={32} />
              </div>
              <h2 className="text-3xl md:text-4xl font-display font-bold mb-6">AI Strategy & Solutions</h2>
              <p className="text-lg text-muted-foreground mb-8 leading-relaxed">
                We move beyond the hype to deliver practical, high-impact AI solutions. By integrating Large Language Models (LLMs) and intelligent agents into your core processes, we help you unlock new insights, enhance customer experiences, and drive competitive advantage.
              </p>
              <ul className="space-y-4 mb-8">
                {[
                  "Strategic AI Implementation (OpenAI, AWS Bedrock, Anthropic, Grok)",
                  "Intelligent Knowledge Management",
                  "AI-Enhanced Customer Engagement",
                  "Data-Driven Decision Support"
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-muted-foreground">
                    <CheckCircle2 size={20} className="text-primary" />
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>
            <div className="order-1 lg:order-2 relative">
               <div className="aspect-square rounded-3xl overflow-hidden glass-panel p-2">
                <img 
                  src="/images/service-ai.png" 
                  alt="AI Strategy" 
                  className="w-full h-full object-cover rounded-2xl"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Service 2: Integration */}
      <section className="py-24 bg-white/5">
        <div className="container px-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div className="relative">
               <div className="aspect-square rounded-3xl overflow-hidden glass-panel p-2">
                <img 
                  src="/images/service-integration.png" 
                  alt="Enterprise Integration" 
                  className="w-full h-full object-cover rounded-2xl"
                />
              </div>
            </div>
            <motion.div 
              initial={{ opacity: 0, x: 50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mb-6 text-primary">
                <Network size={32} />
              </div>
              <h2 className="text-3xl md:text-4xl font-display font-bold mb-6">Enterprise Integration</h2>
              <p className="text-lg text-muted-foreground mb-8 leading-relaxed">
                A disconnected business is an inefficient one. We specialize in unifying your digital ecosystem, ensuring that your systems, data, and teams are perfectly aligned. We build the bridges that allow information to flow freely, enabling real-time agility.
              </p>
              <ul className="space-y-4 mb-8">
                {[
                  "API Strategy & Management",
                  "System Modernization & Migration",
                  "Real-time Data Synchronization",
                  "Scalable Cloud Architecture (AWS, Azure, GCP)"
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-muted-foreground">
                    <CheckCircle2 size={20} className="text-primary" />
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Service 3: Automation */}
      <section className="py-24 relative">
        <div className="container px-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <motion.div 
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="order-2 lg:order-1"
            >
              <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mb-6 text-primary">
                <Workflow size={32} />
              </div>
              <h2 className="text-3xl md:text-4xl font-display font-bold mb-6">Business Automation</h2>
              <p className="text-lg text-muted-foreground mb-8 leading-relaxed">
                Operational efficiency is the foundation of growth. We identify bottlenecks and implement intelligent automation to streamline your workflows. By removing manual friction, we free your team to focus on high-value strategic initiatives.
              </p>
              <ul className="space-y-4 mb-8">
                {[
                  "Process Optimization & Automation (n8n)",
                  "Business Intelligence & Reporting",
                  "Workflow Orchestration",
                  "Operational Efficiency Audits"
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-muted-foreground">
                    <CheckCircle2 size={20} className="text-primary" />
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>
            <div className="order-1 lg:order-2 relative">
               <div className="aspect-square rounded-3xl overflow-hidden glass-panel p-2">
                <img 
                  src="/images/service-automation.png" 
                  alt="Business Automation" 
                  className="w-full h-full object-cover rounded-2xl"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 text-center">
        <div className="container px-4">
          <div className="glass-panel p-12 rounded-3xl max-w-4xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-display font-bold mb-6">Have a specific business challenge?</h2>
            <p className="text-lg text-muted-foreground mb-8">
              We understand that every organization is unique. Let's discuss how we can tailor a solution to your goals.
            </p>
            <Link href="/contact">
              <Button size="lg" className="rounded-full px-8">
                Start the Conversation <ArrowRight className="ml-2" />
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </Layout>
  );
}
