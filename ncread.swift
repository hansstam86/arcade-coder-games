// ncread — watch the macOS Notification Center database and POST each new
// notification to the ArcadeOS webhook. Runs as its OWN app (NCReader.app)
// launched via LaunchServices, so Full Disk Access granted to NCReader.app
// applies to it. Grant FDA to NCReader.app once.

import Foundation
import SQLite3

let WEBHOOK = "http://127.0.0.1:7760/notify"
let STATUS = "http://127.0.0.1:7760/nc_status"

func post(_ url: String, _ obj: [String: Any]) {
    guard let u = URL(string: url),
          let body = try? JSONSerialization.data(withJSONObject: obj) else { return }
    var req = URLRequest(url: u)
    req.httpMethod = "POST"
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    req.httpBody = body
    let sem = DispatchSemaphore(value: 0)
    URLSession.shared.dataTask(with: req) { _, _, _ in sem.signal() }.resume()
    _ = sem.wait(timeout: .now() + 2)
}

let home = FileManager.default.homeDirectoryForCurrentUser
let dbPath = home.appendingPathComponent(
    "Library/Group Containers/group.com.apple.usernoted/db2/db").path

var db: OpaquePointer?
if sqlite3_open_v2(dbPath, &db, SQLITE_OPEN_READONLY, nil) != SQLITE_OK {
    post(STATUS, ["ok": false, "error": String(cString: sqlite3_errmsg(db))])
    exit(2)
}
post(STATUS, ["ok": true])

var lastDelivered = Date().timeIntervalSinceReferenceDate
let query = """
    SELECT a.identifier, r.delivered_date, r.data
    FROM record r JOIN app a ON r.app_id = a.app_id
    WHERE r.delivered_date > ? ORDER BY r.delivered_date
    """

var lastPing = Date()
while true {
    var stmt: OpaquePointer?
    if sqlite3_prepare_v2(db, query, -1, &stmt, nil) == SQLITE_OK {
        sqlite3_bind_double(stmt, 1, lastDelivered)
        while sqlite3_step(stmt) == SQLITE_ROW {
            let ident = sqlite3_column_text(stmt, 0).map { String(cString: $0) } ?? ""
            let delivered = sqlite3_column_double(stmt, 1)
            if delivered > lastDelivered { lastDelivered = delivered }
            var title = "", body = ""
            if let blob = sqlite3_column_blob(stmt, 2) {
                let len = Int(sqlite3_column_bytes(stmt, 2))
                let data = Data(bytes: blob, count: len)
                if let plist = try? PropertyListSerialization.propertyList(
                        from: data, options: [], format: nil) as? [String: Any],
                   let req = plist["req"] as? [String: Any] {
                    title = (req["titl"] as? String) ?? ""
                    body = (req["body"] as? String) ?? ""
                }
            }
            post(WEBHOOK, ["app": ident, "title": title, "body": body])
        }
    }
    sqlite3_finalize(stmt)
    // periodic keepalive so the service knows access is still good
    if Date().timeIntervalSince(lastPing) > 20 {
        post(STATUS, ["ok": true]); lastPing = Date()
    }
    Thread.sleep(forTimeInterval: 1.5)
}
