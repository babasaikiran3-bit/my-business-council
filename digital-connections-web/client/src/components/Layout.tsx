import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Menu, X, Linkedin, Mail, MapPin } from "lucide-react";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function Layout({ children }: { children: React.ReactNode }) {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [location] = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navLinks = [
    { name: "Home", href: "/" },
    { name: "About", href: "/about" },
    { name: "Services", href: "/services" },
    { name: "Technology", href: "/technology" },
    { name: "Innovation", href: "/innovation" },
    { name: "Contact", href: "/contact" },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground font-body selection:bg-primary/30">
      {/* Navigation */}
      <header
        className={cn(
          "fixed top-0 left-0 right-0 z-50 transition-all duration-300 border-b border-transparent",
          isScrolled
            ? "bg-background/80 backdrop-blur-xl border-white/10 py-4"
            : "bg-transparent py-6"
        )}
      >
        <div className="container mx-auto px-4 flex items-center justify-between">
          <Link href="/">
            <div className="flex items-center gap-3 hover:opacity-80 transition-opacity cursor-pointer">
              <img src="/images/logo.png" alt="Dygital Connections Logo" className="h-[100px] w-[100px] object-contain" />
              <span className="text-2xl font-display font-bold tracking-tighter text-gradient">
                Dygital Connections
              </span>
            </div>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <Link key={link.name} href={link.href}>
                <span
                  className={cn(
                    "text-sm font-medium transition-colors hover:text-primary cursor-pointer",
                    location === link.href
                      ? "text-primary"
                      : "text-muted-foreground"
                  )}
                >
                  {link.name}
                </span>
              </Link>
            ))}
            <Link href="/contact">
              <Button className="glass-button rounded-full px-6">
                Get in Touch
              </Button>
            </Link>
          </nav>

          {/* Mobile Menu Toggle */}
          <button
            className="md:hidden text-foreground"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </header>

      {/* Mobile Menu Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed inset-0 z-40 bg-background/95 backdrop-blur-xl pt-24 px-4 md:hidden"
          >
            <nav className="flex flex-col gap-6 items-center">
              {navLinks.map((link) => (
                <Link key={link.name} href={link.href}>
                  <span
                    className="text-2xl font-display font-medium text-foreground hover:text-primary transition-colors cursor-pointer"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {link.name}
                  </span>
                </Link>
              ))}
              <Link href="/contact">
                <Button 
                  className="mt-4 w-full max-w-xs rounded-full bg-primary text-primary-foreground hover:bg-primary/90"
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  Get in Touch
                </Button>
              </Link>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main className="flex-grow pt-0">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-black/40 border-t border-white/5 py-16 backdrop-blur-lg">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
            <div className="col-span-1 md:col-span-2">
              <h3 className="text-2xl font-display font-bold mb-4 text-gradient">
                Dygital Connections
              </h3>
              <p className="text-muted-foreground max-w-md mb-6 leading-relaxed">
                Boutique IT AI, Integration & Automation Consultancy.
                Thriving in Australia with South African Roots.
                Driven by the Spirit of Ubuntu.
              </p>
              <div className="flex gap-4">
                <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className="p-2 rounded-full bg-white/5 hover:bg-white/10 transition-colors text-foreground">
                  <Linkedin size={20} />
                </a>
                <a href="mailto:contact@digitalconnections.com" className="p-2 rounded-full bg-white/5 hover:bg-white/10 transition-colors text-foreground">
                  <Mail size={20} />
                </a>
              </div>
            </div>
            
            <div>
              <h4 className="font-display font-semibold mb-4 text-foreground">Services</h4>
              <ul className="space-y-3 text-muted-foreground">
                <li><Link href="/services"><span className="hover:text-primary transition-colors cursor-pointer">AI Solutions</span></Link></li>
                <li><Link href="/services"><span className="hover:text-primary transition-colors cursor-pointer">System Integration</span></Link></li>
                <li><Link href="/services"><span className="hover:text-primary transition-colors cursor-pointer">Workflow Automation</span></Link></li>
                <li><Link href="/technology"><span className="hover:text-primary transition-colors cursor-pointer">Technology Stack</span></Link></li>
              </ul>
            </div>

            <div>
              <h4 className="font-display font-semibold mb-4 text-foreground">Company</h4>
              <ul className="space-y-3 text-muted-foreground">
                <li><Link href="/about"><span className="hover:text-primary transition-colors cursor-pointer">About Us</span></Link></li>
                <li><Link href="/about"><span className="hover:text-primary transition-colors cursor-pointer">Ubuntu Philosophy</span></Link></li>
                <li><Link href="/contact"><span className="hover:text-primary transition-colors cursor-pointer">Contact</span></Link></li>
                <li className="flex items-center gap-2 mt-4 text-sm">
                  <MapPin size={14} /> 2/14 Edgewater Court, Robina
                </li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-white/5 pt-8 flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
            <p>&copy; {new Date().getFullYear()} Dygital Connections. All rights reserved.</p>
            <p className="italic">"I am because we are"</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
