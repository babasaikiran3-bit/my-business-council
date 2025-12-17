import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { ArrowRight, Cpu, Network, Workflow, Users, Globe } from "lucide-react";
import { Link } from "wouter";

export default function Home() {
  const fadeInUp = {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] }
  };

  const staggerContainer = {
    animate: {
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  return (
    <Layout>
      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
        {/* Background Elements */}
        <div className="absolute inset-0 z-0">
          <img 
            src="/images/hero-bg.png" 
            alt="Abstract Glass Background" 
            className="w-full h-full object-cover opacity-80"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-background/20 via-background/60 to-background" />
        </div>

        <div className="container relative z-10 px-4 text-center">
          <motion.div
            initial="initial"
            animate="animate"
            variants={staggerContainer}
            className="max-w-4xl mx-auto"
          >
            <motion.div variants={fadeInUp} className="mb-6 inline-block">
              <span className="px-4 py-1.5 rounded-full glass-panel text-sm font-medium text-primary-foreground/90 border border-primary/20">
                Boutique IT AI, Integration & Automation Consultancy
              </span>
            </motion.div>
            
            <motion.h1 variants={fadeInUp} className="text-5xl md:text-7xl lg:text-8xl font-display font-bold tracking-tight mb-8 text-gradient leading-[1.1]">
              Connectedness through <br />
              <span className="text-gradient-accent">Technology</span>
            </motion.h1>
            
            <motion.p variants={fadeInUp} className="text-xl md:text-2xl text-muted-foreground mb-10 max-w-2xl mx-auto leading-relaxed">
              Inspired by the Spirit of Ubuntu, an ancient South African term meaning "I am because we are."
            </motion.p>
            
            <motion.div variants={fadeInUp} className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href="/contact">
                <Button size="lg" className="rounded-full text-lg px-8 h-14 bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20">
                  Start a Conversation <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link href="/about">
                <Button size="lg" variant="outline" className="rounded-full text-lg px-8 h-14 glass-button hover:bg-white/10">
                  Our Philosophy
                </Button>
              </Link>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Philosophy Section */}
      <section className="py-24 relative overflow-hidden">
        <div className="container px-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <motion.div 
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
              className="relative"
            >
              <div className="aspect-square rounded-3xl overflow-hidden glass-panel p-2">
                <img 
                  src="/images/about-ubuntu.png" 
                  alt="Ubuntu Philosophy" 
                  className="w-full h-full object-cover rounded-2xl"
                />
              </div>
              {/* Floating Badge */}
              <div className="absolute -bottom-6 -right-6 glass-panel p-6 rounded-2xl max-w-xs animate-float">
                <p className="font-display font-bold text-xl mb-1">Ubuntu</p>
                <p className="text-sm text-muted-foreground">"I am because we are"</p>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, x: 50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8 }}
            >
              <h2 className="text-4xl md:text-5xl font-display font-bold mb-6">
                People First. <br />
                <span className="text-gradient-accent">Business Driven.</span>
              </h2>
              <p className="text-lg text-muted-foreground mb-6 leading-relaxed">
                At Dygital Connections, we believe that technology is a means to an end—better business outcomes and stronger human connections. Our philosophy is deeply rooted in the spirit of Ubuntu, an ancient South African term emphasizing that success is a collective achievement.
              </p>
              <p className="text-lg text-muted-foreground mb-8 leading-relaxed">
                Inspired by the collaborative power of the open-source movement, we build integrated solutions that don't just function—they empower. We bridge the gap between complex technical systems and the strategic goals of your organization.
              </p>
              
              <div className="grid grid-cols-2 gap-6">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <Users size={24} />
                  </div>
                  <div>
                    <h4 className="font-bold mb-1">Partnership</h4>
                    <p className="text-sm text-muted-foreground">Building lasting value</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <Globe size={24} />
                  </div>
                  <div>
                    <h4 className="font-bold mb-1">Global Perspective</h4>
                    <p className="text-sm text-muted-foreground">SA Heritage, AU Thriving</p>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section className="py-24 bg-white/5 backdrop-blur-sm">
        <div className="container px-4">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-4xl md:text-5xl font-display font-bold mb-6">Strategic Capabilities</h2>
            <p className="text-lg text-muted-foreground">
              We deliver business value through three core pillars of digital transformation.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Service 1 */}
            <motion.div 
              whileHover={{ y: -10 }}
              className="glass-panel p-8 rounded-3xl relative group overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                <Cpu size={120} />
              </div>
              <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mb-6 text-primary">
                <Cpu size={32} />
              </div>
              <h3 className="text-2xl font-display font-bold mb-4">AI Strategy</h3>
              <p className="text-muted-foreground mb-6 leading-relaxed">
                Leveraging cutting-edge Large Language Models (LLMs) and AI agents to solve complex business problems and enhance strategic decision-making.
              </p>
              <Link href="/services">
                <span className="inline-flex items-center text-primary font-medium hover:underline cursor-pointer">
                  Explore Solutions <ArrowRight size={16} className="ml-2" />
                </span>
              </Link>
            </motion.div>

            {/* Service 2 */}
            <motion.div 
              whileHover={{ y: -10 }}
              className="glass-panel p-8 rounded-3xl relative group overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                <Network size={120} />
              </div>
              <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mb-6 text-primary">
                <Network size={32} />
              </div>
              <h3 className="text-2xl font-display font-bold mb-4">Enterprise Integration</h3>
              <p className="text-muted-foreground mb-6 leading-relaxed">
                Seamlessly connecting disparate systems and data sources to ensure your digital ecosystem operates as a unified, efficient business engine.
              </p>
              <Link href="/services">
                <span className="inline-flex items-center text-primary font-medium hover:underline cursor-pointer">
                  Connect Systems <ArrowRight size={16} className="ml-2" />
                </span>
              </Link>
            </motion.div>

            {/* Service 3 */}
            <motion.div 
              whileHover={{ y: -10 }}
              className="glass-panel p-8 rounded-3xl relative group overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                <Workflow size={120} />
              </div>
              <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mb-6 text-primary">
                <Workflow size={32} />
              </div>
              <h3 className="text-2xl font-display font-bold mb-4">Business Automation</h3>
              <p className="text-muted-foreground mb-6 leading-relaxed">
                Streamlining workflows with intelligent automation. We remove operational friction so your team can focus on high-value strategic initiatives.
              </p>
              <Link href="/services">
                <span className="inline-flex items-center text-primary font-medium hover:underline cursor-pointer">
                  Optimize Workflows <ArrowRight size={16} className="ml-2" />
                </span>
              </Link>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-32 relative overflow-hidden">
        <div className="absolute inset-0 z-0">
           <div className="absolute inset-0 bg-gradient-to-t from-primary/20 to-transparent opacity-30" />
        </div>
        <div className="container relative z-10 px-4 text-center">
          <h2 className="text-4xl md:text-6xl font-display font-bold mb-8">
            Ready to <span className="text-gradient-accent">Transform?</span>
          </h2>
          <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto">
            Let's discuss how we can bring strategic innovation and the spirit of Ubuntu, an ancient South African philosophy, to your business.
          </p>
          <Link href="/contact">
            <Button size="lg" className="rounded-full text-lg px-10 h-16 bg-primary hover:bg-primary/90 text-primary-foreground shadow-xl shadow-primary/20 transition-transform hover:scale-105">
              Get in Touch
            </Button>
          </Link>
        </div>
      </section>
    </Layout>
  );
}
