import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 rounded-2xl bg-white p-10 text-center shadow-card">
          <div className="text-5xl">🐦</div>
          <h2 className="text-xl font-bold text-red-600">Something went wrong</h2>
          <p className="max-w-md text-sm text-slate-500">
            {this.state.error?.message || 'An unexpected error occurred. Try refreshing the page.'}
          </p>
          <div className="flex gap-3">
            <button
              onClick={this.handleReset}
              className="rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-90"
            >
              Try again
            </button>
            <button
              onClick={() => window.location.assign('/')}
              className="rounded-xl border px-5 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
            >
              Go home
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
