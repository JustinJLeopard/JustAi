import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  createTrajectoryMiddleware,
  listTrajectoryFiles,
  parseTrajectoryRequestPath,
  readTrajectoryFile,
} from './trajectory-middleware'

let root: string
let outside: string

function invokeMiddleware(url: string, method = 'GET') {
  const headers = new Map<string, string>()
  let body: string | Buffer | undefined
  const response = {
    statusCode: 200,
    setHeader(name: string, value: string) {
      headers.set(name.toLowerCase(), value)
    },
    end(value?: string | Buffer) {
      body = value
    },
  } as unknown as ServerResponse

  createTrajectoryMiddleware([root])({ url, method } as IncomingMessage, response)
  return { statusCode: response.statusCode, headers, body }
}

beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'justai-trajectories-'))
  outside = path.join(os.tmpdir(), `outside-${path.basename(root)}.traj.json`)
  fs.writeFileSync(path.join(root, 'direct.traj.json'), '{"source":"direct"}')
  fs.mkdirSync(path.join(root, 'relay_dispatch'))
  fs.writeFileSync(path.join(root, 'relay_dispatch', 'relay.traj.json'), '{"source":"relay"}')
  fs.writeFileSync(outside, '{"source":"outside"}')
})

afterEach(() => {
  fs.rmSync(root, { recursive: true, force: true })
  fs.rmSync(outside, { force: true })
})

describe('trajectory middleware path containment', () => {
  it('accepts the direct and relay file shapes used by the dashboard', () => {
    expect(parseTrajectoryRequestPath('/direct.traj.json')).toEqual(['direct.traj.json'])
    expect(parseTrajectoryRequestPath('/relay_dispatch%2Frelay.traj.json')).toEqual([
      'relay_dispatch',
      'relay.traj.json',
    ])
    expect(readTrajectoryFile([root], '/direct.traj.json')?.toString()).toContain('direct')
    expect(readTrajectoryFile([root], '/relay_dispatch%2Frelay.traj.json')?.toString()).toContain('relay')
  })

  it('rejects traversal, malformed escapes, absolute paths, and arbitrary directories', () => {
    const outsideName = path.basename(outside)
    for (const candidate of [
      `/..%2F${outsideName}`,
      `/%2e%2e%2f${outsideName}`,
      `/%252e%252e%252f${outsideName}`,
      `/${encodeURIComponent(outside)}`,
      '/relay_dispatch%2F..%2Fdirect.traj.json',
      '/nested%2Fdirect.traj.json',
      '/C%3Adirect.traj.json',
      '/..%5Cdirect.traj.json',
      '/%00direct.traj.json',
      '//direct.traj.json',
      '/bad%ZZ.traj.json',
      '/direct.json',
    ]) {
      expect(readTrajectoryFile([root], candidate)).toBeNull()
      expect(invokeMiddleware(candidate).statusCode).toBe(404)
    }
  })

  it('does not follow symlinked files or relay directories when reading or listing', () => {
    fs.symlinkSync(outside, path.join(root, 'escape.traj.json'))
    fs.renameSync(path.join(root, 'relay_dispatch'), path.join(root, 'real-relay'))
    fs.symlinkSync(path.dirname(outside), path.join(root, 'relay_dispatch'))
    fs.mkdirSync(path.join(root, 'directory.traj.json'))

    expect(readTrajectoryFile([root], '/escape.traj.json')).toBeNull()
    expect(readTrajectoryFile([root], `/relay_dispatch%2F${path.basename(outside)}`)).toBeNull()
    expect(listTrajectoryFiles([root]).map((file) => file.name)).toEqual(['direct.traj.json'])
  })

  it('serves descriptor-backed contents and only lists regular trajectory files', () => {
    const loaded = invokeMiddleware('/direct.traj.json')
    expect(loaded.statusCode).toBe(200)
    expect(loaded.headers.get('content-type')).toMatch(/^application\/json/)
    expect(Buffer.from(loaded.body!).toString()).toContain('direct')

    const listed = invokeMiddleware('/')
    expect(listed.statusCode).toBe(200)
    expect(JSON.parse(String(listed.body)).map((file: { name: string }) => file.name)).toEqual([
      'direct.traj.json',
      'relay_dispatch/relay.traj.json',
    ])
  })

  it('does not expose the filesystem through unsupported HTTP methods', () => {
    const response = invokeMiddleware('/direct.traj.json', 'POST')
    expect(response.statusCode).toBe(405)
    expect(response.headers.get('allow')).toBe('GET, HEAD')
  })
})
