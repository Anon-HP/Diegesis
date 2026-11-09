import { About } from '@/components/about'
import { AnalysisWorkspace } from '@/components/analysis/analysis-workspace'
import { Footer } from '@/components/footer'
import { Hero } from '@/components/hero'
import { HowItWorks } from '@/components/how-it-works'
import { Navbar } from '@/components/navbar'

export default function Page() {
  return (
    <div id="top" className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <AnalysisWorkspace />
        <HowItWorks />
        <About />
      </main>
      <Footer />
    </div>
  )
}
