import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { motion } from "framer-motion";
import { Mail, MapPin, Linkedin, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

export default function Contact() {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    
    // Simulate form submission
    setTimeout(() => {
      setIsSubmitting(false);
      toast.success("Message sent successfully! We'll be in touch soon.");
      // Reset form logic would go here
    }, 1500);
  };

  return (
    <Layout>
      <section className="pt-32 pb-16">
        <div className="container px-4 text-center">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-5xl md:text-7xl font-display font-bold mb-6"
          >
            Get in <span className="text-gradient-accent">Touch</span>
          </motion.h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Whether you have a specific project in mind or just want to explore what's possible with AI and automation, we'd love to hear from you.
          </p>
        </div>
      </section>

      <section className="py-16">
        <div className="container px-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 max-w-6xl mx-auto">
            {/* Contact Info */}
            <motion.div 
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
            >
              <h2 className="text-3xl font-display font-bold mb-8">Contact Information</h2>
              
              <div className="space-y-8">
                <div className="flex items-start gap-6">
                  <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center text-primary shrink-0">
                    <Mail size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2">Email Us</h3>
                    <p className="text-muted-foreground mb-2">For general inquiries and project discussions:</p>
                    <a href="mailto:contact@dygitalconnections.com" className="text-primary hover:underline text-lg">
                      contact@dygitalconnections.com
                    </a>
                  </div>
                </div>

                <div className="flex items-start gap-6">
                  <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center text-primary shrink-0">
                    <Linkedin size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2">Connect on LinkedIn</h3>
                    <p className="text-muted-foreground mb-2">Follow our journey and updates:</p>
                    <a href="https://linkedin.com/in/kevin-dyer-7408002a/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline text-lg">
                      Kevin Dyer
                    </a>
                  </div>
                </div>

                <div className="flex items-start gap-6">
                  <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center text-primary shrink-0">
                    <MapPin size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2">Location</h3>
                    <p className="text-muted-foreground">
                      2/14 Edgewater Court<br />
                      Robina, QLD 4226<br />
                      Australia 🇦🇺
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>

            <div className="flex flex-col gap-8">
              {/* Office Image */}
              <motion.div
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 }}
                className="h-[300px] rounded-3xl overflow-hidden border border-white/10 relative group"
              >
                <img 
                  src="/images/robina-office.webp" 
                  alt="Dygital Connections Office at Robina" 
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent" />
                <div className="absolute bottom-6 left-6 right-6">
                  <p className="text-sm font-medium text-white/90 bg-black/50 backdrop-blur-md p-3 rounded-xl inline-block border border-white/10">
                    Visit us at our Robina HQ
                  </p>
                </div>
              </motion.div>

              {/* Contact Form */}
              <motion.div 
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5 }}
                className="glass-panel p-8 md:p-10 rounded-3xl"
              >
              <h2 className="text-2xl font-bold mb-6">Send us a Message</h2>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label htmlFor="name" className="text-sm font-medium ml-1">Name</label>
                    <Input id="name" placeholder="Your name" required className="bg-white/5 border-white/10 focus:border-primary/50 h-12 rounded-xl" />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="email" className="text-sm font-medium ml-1">Email</label>
                    <Input id="email" type="email" placeholder="your@email.com" required className="bg-white/5 border-white/10 focus:border-primary/50 h-12 rounded-xl" />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <label htmlFor="subject" className="text-sm font-medium ml-1">Subject</label>
                  <Input id="subject" placeholder="What's this about?" required className="bg-white/5 border-white/10 focus:border-primary/50 h-12 rounded-xl" />
                </div>

                <div className="space-y-2">
                  <label htmlFor="message" className="text-sm font-medium ml-1">Message</label>
                  <Textarea id="message" placeholder="Tell us about your project or inquiry..." required className="bg-white/5 border-white/10 focus:border-primary/50 min-h-[150px] rounded-xl resize-none" />
                </div>

                <Button 
                  type="submit" 
                  disabled={isSubmitting}
                  className="w-full h-12 rounded-xl text-lg font-medium bg-primary hover:bg-primary/90 text-primary-foreground"
                >
                  {isSubmitting ? "Sending..." : (
                    <span className="flex items-center justify-center gap-2">
                      Send Message <Send size={18} />
                    </span>
                  )}
                </Button>
              </form>
            </motion.div>
            </div>
          </div>
        </div>
      </section>
    </Layout>
  );
}
