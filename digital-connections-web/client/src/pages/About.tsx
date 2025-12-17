import Layout from "@/components/Layout";
import { motion } from "framer-motion";
import { Heart, Globe, Users, Lightbulb } from "lucide-react";

export default function About() {
  return (
    <Layout>
      {/* Header */}
      <section className="pt-32 pb-16 relative overflow-hidden">
        <div className="container px-4 text-center">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-5xl md:text-7xl font-display font-bold mb-6"
          >
            Our <span className="text-gradient-accent">Story</span>
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed"
          >
            From the vibrant landscapes of South Africa to the thriving tech ecosystem of Australia, our journey is defined by connection.
          </motion.p>
        </div>
      </section>

      {/* The Ubuntu Philosophy */}
      <section className="py-16">
        <div className="container px-4">
          <div className="glass-panel rounded-3xl p-8 md:p-16 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-primary/10 to-transparent pointer-events-none" />
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center relative z-10">
              <div>
                <h2 className="text-3xl md:text-4xl font-display font-bold mb-6">The Spirit of Ubuntu</h2>
                <blockquote className="text-2xl font-light italic border-l-4 border-primary pl-6 mb-8 text-muted-foreground">
                  "I am because we are."
                </blockquote>
                <p className="text-lg text-muted-foreground mb-6 leading-relaxed">
                  Ubuntu is an ancient South African term that means "I am because we are." It is a philosophy that defines our existence through our interactions with others. In business, this translates to a deep understanding that no company, no team, and no solution exists in isolation.
                </p>
                <p className="text-lg text-muted-foreground leading-relaxed">
                  Following on from this, we draw inspiration from the open source Linux movement, which adopted this name to represent the spirit of sharing and collaboration in software. Just as the Linux community builds better systems through collective effort, we build better business solutions through deep partnership and integration.
                </p>
              </div>
              <div className="relative h-[400px] rounded-2xl overflow-hidden glass-panel">
                 <img 
                  src="/images/about-ubuntu.png" 
                  alt="Ubuntu Connection" 
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Values Grid */}
      <section className="py-24">
        <div className="container px-4">
          <h2 className="text-3xl md:text-4xl font-display font-bold mb-16 text-center">Core Values</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              {
                icon: <Users size={32} />,
                title: "People First",
                desc: "Technology is the enabler, but people are the purpose. We design solutions that empower teams."
              },
              {
                icon: <Globe size={32} />,
                title: "Connectedness",
                desc: "Bridging gaps between business strategy and technical execution."
              },
              {
                icon: <Heart size={32} />,
                title: "Partnership",
                desc: "We don't just deliver projects; we build lasting relationships rooted in shared success."
              },
              {
                icon: <Lightbulb size={32} />,
                title: "Strategic Innovation",
                desc: "Applying modern AI not just for novelty, but to solve real business challenges."
              }
            ].map((value, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="glass-panel p-8 rounded-2xl hover:bg-white/5 transition-colors"
              >
                <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center mb-6 text-primary">
                  {value.icon}
                </div>
                <h3 className="text-xl font-bold mb-3">{value.title}</h3>
                <p className="text-muted-foreground leading-relaxed">
                  {value.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Kevin's Profile Section (Inspiration) */}
      <section className="py-24 bg-white/5">
        <div className="container px-4">
          <div className="max-w-4xl mx-auto text-center">
            <div className="w-32 h-32 mx-auto rounded-full bg-gradient-to-br from-primary to-purple-600 mb-8 p-1">
              <div className="w-full h-full rounded-full bg-background overflow-hidden">
                 {/* Placeholder for profile image if available, or abstract avatar */}
                 <div className="w-full h-full flex items-center justify-center bg-zinc-800 text-4xl font-bold">KD</div>
              </div>
            </div>
            <h2 className="text-3xl md:text-4xl font-display font-bold mb-4">Led by Experience</h2>
            <p className="text-xl text-muted-foreground mb-8">
              With deep roots in distributed architectures and building high-performing teams, our leadership combines decades of systems expertise with a strategic vision for modern AI integration. We bridge the gap between technical complexity and business value, fostering agile, people-focused environments where innovation drives tangible results.
            </p>
          </div>
        </div>
      </section>
    </Layout>
  );
}
