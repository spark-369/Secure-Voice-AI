import { useCallback, useEffect, useState } from 'react'

import { useToast } from '../../app/providers/ToastProvider.jsx'
import Button from '../../components/ui/Button.jsx'
import ConfirmDialog from '../../components/ui/ConfirmDialog.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Input, { Textarea } from '../../components/ui/Input.jsx'
import Spinner from '../../components/ui/Spinner.jsx'
import { api } from '../../lib/api.js'

const emptyDoc = { title: '', source: '', content: '' }

/** Admin-only knowledge-base console: seed defaults, CRUD documents, inspect the index. */
export default function KnowledgePage() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [draft, setDraft] = useState(emptyDoc)
  const [editingId, setEditingId] = useState(null)
  const [deletingDoc, setDeletingDoc] = useState(null)
  const [edit, setEdit] = useState(emptyDoc)

  const load = useCallback(async () => {
    try {
      const [statsData, docs] = await Promise.all([api.knowledgeStats(), api.listDocuments()])
      setStats(statsData)
      setDocuments(docs)
    } catch (err) {
      toast.error(err.message || 'Failed to load the knowledge base')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const seedDefault = async () => {
    setBusy(true)
    try {
      const result = await api.ingestDefault()
      toast.success(
        result.queued
          ? `Queued ${result.documents} document(s) — the index updates in a moment.`
          : `Ingested ${result.documents} document(s).`,
      )
      setTimeout(load, 2500)
    } catch (err) {
      toast.error(err.message || 'Seeding failed')
    } finally {
      setBusy(false)
    }
  }

  const addDocument = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api.ingestDocuments({
        documents: [
          { title: draft.title.trim(), source: draft.source.trim(), content: draft.content },
        ],
      })
      toast.success('Document added — it will appear in the list shortly.')
      setDraft(emptyDoc)
      setShowForm(false)
      setTimeout(load, 2500)
    } catch (err) {
      toast.error(err.message || 'Ingestion failed')
    } finally {
      setBusy(false)
    }
  }

  const saveEdit = async (documentId) => {
    if (!edit.title.trim() || !edit.content.trim()) return
    setBusy(true)
    try {
      await api.updateDocument(documentId, {
        title: edit.title.trim(),
        source: edit.source.trim(),
        content: edit.content,
      })
      toast.success('Document updated — the knowledge base is being refreshed.')
      setEditingId(null)
      setTimeout(load, 2500)
    } catch (err) {
      toast.error(err.message || 'Update failed')
    } finally {
      setBusy(false)
    }
  }

  const openDeleteDoc = (doc) => setDeletingDoc(doc)

  const deleteDoc = async () => {
    if (!deletingDoc) return
    setBusy(true)
    try {
      await api.deleteDocument(deletingDoc.id)
      toast.success('Document deleted.')
      if (editingId === deletingDoc.id) setEditingId(null)
      await load()
    } catch (err) {
      toast.error(err.message || 'Delete failed')
    } finally {
      setBusy(false)
      setDeletingDoc(null)
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Knowledge base</h2>
          <p className="text-xs text-slate-400">
            Admin only — the agent answers customers using these documents.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={seedDefault} disabled={busy} className="whitespace-nowrap">
            {busy ? 'Working…' : 'Seed default knowledge base'}
          </Button>
          <Button variant="outline" onClick={() => setShowForm((value) => !value)} className="whitespace-nowrap">
            {showForm ? 'Close form' : 'Add document'}
          </Button>
        </div>
      </div>

      <div className="grid max-w-md grid-cols-2 gap-3">
        {[
          { label: 'Documents', value: stats?.documents ?? '—' },
          { label: 'Indexed sections', value: stats?.indexed_chunks ?? '—' },
        ].map((card) => (
          <div key={card.label} className="rounded-2xl border border-slate-800/70 bg-slate-900/40 p-4">
            <p className="text-2xl font-semibold text-cyan-300">{card.value}</p>
            <p className="mt-1 text-xs text-slate-400">{card.label}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <form
          onSubmit={addDocument}
          className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-900/40 p-4"
        >
          <Input
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            placeholder="Title (e.g. Refund policy)"
            required
          />
          <Input
            value={draft.source}
            onChange={(e) => setDraft({ ...draft, source: e.target.value })}
            placeholder="Source (optional, e.g. policies/refunds.md)"
          />
          <Textarea
            value={draft.content}
            onChange={(e) => setDraft({ ...draft, content: e.target.value })}
            placeholder="Document content…"
            required
            rows={6}
          />
          <Button type="submit" variant="solid" disabled={busy}>
            Add to knowledge base
          </Button>
        </form>
      )}

      {loading ? (
        <Spinner label="Loading knowledge base…" />
      ) : documents.length === 0 ? (
        <EmptyState
          icon="📚"
          title="No documents yet"
          hint="Seed the default knowledge base (or add documents) to ground the agent's answers."
        />
      ) : (
        <ul className="space-y-2">
          {documents.map((doc) =>
            editingId === doc.id ? (
              <li
                key={doc.id}
                className="space-y-3 rounded-2xl border border-indigo-500/40 bg-slate-900/60 p-4"
              >
                <Input value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} placeholder="Title" />
                <Input value={edit.source} onChange={(e) => setEdit({ ...edit, source: e.target.value })} placeholder="Source" />
                <Textarea value={edit.content} onChange={(e) => setEdit({ ...edit, content: e.target.value })} rows={6} />
                <div className="flex gap-2">
                  <Button
                    variant="solid"
                    onClick={() => saveEdit(doc.id)}
                    disabled={busy || !edit.title.trim() || !edit.content.trim()}
                  >
                    {busy ? 'Saving…' : 'Save changes'}
                  </Button>
                  <Button variant="outline" onClick={() => setEditingId(null)}>
                    Cancel
                  </Button>
                </div>
              </li>
            ) : (
              <li
                key={doc.id}
                className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-800/70 bg-slate-900/40 px-4 py-3"
              >
                <span className="min-w-0 max-w-full truncate text-sm font-medium text-slate-100">
                  {doc.title}
                </span>
                <span className="text-xs text-slate-500">{doc.source || 'no source'}</span>
                <span className="ml-auto text-xs text-slate-500">
                  {doc.chunk_count} sections
                </span>
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditingId(doc.id)
                    setEdit({ title: doc.title, source: doc.source || '', content: doc.content || '' })
                  }}
                >
                  Edit
                </Button>
                <Button variant="danger" onClick={() => openDeleteDoc(doc)} disabled={busy}>
                  Delete
                </Button>
              </li>
            ),
          )}
        </ul>
      )}

      <ConfirmDialog
        open={deletingDoc !== null}
        title={`Delete "${deletingDoc?.title || 'this document'}"?`}
        message="Its vector chunks are removed from the RAG index, so the agent will no longer use this content."
        confirmLabel="Delete document"
        busy={busy}
        onConfirm={deleteDoc}
        onCancel={() => setDeletingDoc(null)}
      />
    </section>
  )
}

