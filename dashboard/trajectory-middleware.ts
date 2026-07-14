import fs from 'node:fs'
import path from 'node:path'
import type { IncomingMessage, ServerResponse } from 'node:http'

const TRAJECTORY_SUFFIX = '.traj.json'
const RELAY_DISPATCH_DIRECTORY = 'relay_dispatch'

export type TrajectoryFile = {
  name: string
  size: number
  mtime: string
}

/**
 * Accept only the two trajectory shapes the dashboard understands.  This is
 * deliberately stricter than a generic relative-path check: callers can load
 * a root trajectory or one in relay_dispatch, but cannot choose a directory.
 */
export function parseTrajectoryRequestPath(requestUrl: string | undefined): string[] | null {
  const rawPath = (requestUrl ?? '').split(/[?#]/, 1)[0]
  if (!rawPath || rawPath === '/') return null

  const encodedPath = rawPath.startsWith('/') ? rawPath.slice(1) : rawPath
  if (!encodedPath) return null

  let decodedPath: string
  try {
    decodedPath = decodeURIComponent(encodedPath)
  } catch {
    return null
  }

  if (
    !decodedPath
    || decodedPath.includes('\0')
    || decodedPath.includes('\\')
    || decodedPath.includes(':')
    || path.isAbsolute(decodedPath)
  ) {
    return null
  }

  const parts = decodedPath.split('/')
  if (parts.some((part) => !part || part === '.' || part === '..')) return null
  if (!parts.at(-1)?.endsWith(TRAJECTORY_SUFFIX)) return null

  if (parts.length === 1) return parts
  if (parts.length === 2 && parts[0] === RELAY_DISPATCH_DIRECTORY) return parts
  return null
}

function secureOpenFlags(directory: boolean): number | null {
  const { O_RDONLY, O_NONBLOCK, O_NOFOLLOW, O_DIRECTORY } = fs.constants
  if (
    process.platform !== 'linux'
    || !fs.existsSync('/proc/self/fd')
    || !Number.isInteger(O_NOFOLLOW)
    || !Number.isInteger(O_NONBLOCK)
    || (directory && !Number.isInteger(O_DIRECTORY))
  ) {
    return null
  }
  return O_RDONLY | O_NONBLOCK | O_NOFOLLOW | (directory ? O_DIRECTORY : 0)
}

function fdChildPath(parentFd: number, child: string): string {
  return `/proc/self/fd/${parentFd}/${child}`
}

function openDirectory(target: string, parentFd?: number): number | null {
  const flags = secureOpenFlags(true)
  if (flags === null) return null

  let fd: number | null = null
  try {
    fd = fs.openSync(parentFd === undefined ? target : fdChildPath(parentFd, target), flags)
    if (!fs.fstatSync(fd).isDirectory()) throw new Error('not a directory')
    return fd
  } catch {
    if (fd !== null) fs.closeSync(fd)
    return null
  }
}

function openRegularFile(filename: string, parentFd: number): number | null {
  const flags = secureOpenFlags(false)
  if (flags === null) return null

  let fd: number | null = null
  try {
    fd = fs.openSync(fdChildPath(parentFd, filename), flags)
    if (!fs.fstatSync(fd).isFile()) throw new Error('not a regular file')
    return fd
  } catch {
    if (fd !== null) fs.closeSync(fd)
    return null
  }
}

function openConfiguredRoot(directory: string): number | null {
  try {
    // Resolving the configured root is an administrator-controlled operation;
    // subsequent user-controlled components are opened through directory FDs.
    return openDirectory(fs.realpathSync.native(directory))
  } catch {
    return null
  }
}

function listDirectoryFiles(directoryFd: number, prefix = ''): TrajectoryFile[] {
  const files: TrajectoryFile[] = []
  let entries: fs.Dirent[]
  try {
    entries = fs.readdirSync(fdChildPath(directoryFd, ''), { withFileTypes: true })
  } catch {
    return files
  }

  for (const entry of entries) {
    if (!entry.name.endsWith(TRAJECTORY_SUFFIX)) continue
    const fd = openRegularFile(entry.name, directoryFd)
    if (fd === null) continue
    try {
      const stat = fs.fstatSync(fd)
      files.push({
        name: prefix ? `${prefix}/${entry.name}` : entry.name,
        size: stat.size,
        mtime: stat.mtime.toISOString(),
      })
    } finally {
      fs.closeSync(fd)
    }
  }
  return files
}

export function listTrajectoryFiles(trajectoryDirectories: readonly string[]): TrajectoryFile[] {
  const files: TrajectoryFile[] = []

  for (const directory of trajectoryDirectories) {
    const rootFd = openConfiguredRoot(directory)
    if (rootFd === null) continue
    try {
      files.push(...listDirectoryFiles(rootFd))
      const relayFd = openDirectory(RELAY_DISPATCH_DIRECTORY, rootFd)
      if (relayFd !== null) {
        try {
          files.push(...listDirectoryFiles(relayFd, RELAY_DISPATCH_DIRECTORY))
        } finally {
          fs.closeSync(relayFd)
        }
      }
    } finally {
      fs.closeSync(rootFd)
    }
  }

  return files.sort((left, right) => right.mtime.localeCompare(left.mtime))
}

export function readTrajectoryFile(
  trajectoryDirectories: readonly string[],
  requestUrl: string | undefined,
): Buffer | null {
  const parts = parseTrajectoryRequestPath(requestUrl)
  if (parts === null) return null

  for (const directory of trajectoryDirectories) {
    const rootFd = openConfiguredRoot(directory)
    if (rootFd === null) continue
    let relayFd: number | null = null
    try {
      const parentFd = parts.length === 2
        ? (relayFd = openDirectory(RELAY_DISPATCH_DIRECTORY, rootFd))
        : rootFd
      if (parentFd === null) continue

      const fileFd = openRegularFile(parts.at(-1)!, parentFd)
      if (fileFd === null) continue
      try {
        // Read from the already-validated descriptor; never reopen a pathname.
        return fs.readFileSync(fileFd)
      } finally {
        fs.closeSync(fileFd)
      }
    } finally {
      if (relayFd !== null) fs.closeSync(relayFd)
      fs.closeSync(rootFd)
    }
  }

  return null
}

export type TrajectoryMiddleware = (
  req: IncomingMessage,
  res: ServerResponse,
) => void

export function createTrajectoryMiddleware(
  trajectoryDirectories: readonly string[],
): TrajectoryMiddleware {
  return (req, res) => {
    const method = (req.method ?? 'GET').toUpperCase()
    if (method !== 'GET' && method !== 'HEAD') {
      res.statusCode = 405
      res.setHeader('Allow', 'GET, HEAD')
      res.end('Method not allowed')
      return
    }

    const rawPath = (req.url ?? '').split(/[?#]/, 1)[0]
    if (!rawPath || rawPath === '/') {
      res.setHeader('Content-Type', 'application/json; charset=utf-8')
      res.end(method === 'HEAD' ? undefined : JSON.stringify(listTrajectoryFiles(trajectoryDirectories)))
      return
    }

    const content = readTrajectoryFile(trajectoryDirectories, req.url)
    if (content === null) {
      res.statusCode = 404
      res.end('Not found')
      return
    }

    res.setHeader('Content-Type', 'application/json; charset=utf-8')
    res.end(method === 'HEAD' ? undefined : content)
  }
}
