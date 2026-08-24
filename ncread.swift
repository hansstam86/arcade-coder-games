// ncread — watch the macOS Notification Center database and print each new
// notification as a JSON line on stdout. Grant THIS binary Full Disk Access
// (System Settings > Privacy & Security > Full Disk Access > add ncread_helper).
//
//   swiftc -O ncread.swift -o ncread_helper -lsqlite3
//   ./ncread_helper           # {"app":"...","title":"...","body":"..."} per line

import Foundation
import SQLite3

func elog(_ s: String) {
    FileHandle.standardError.write((s + "\n").data(using: .utf8)!)
}

let home = FileManager.default.homeDirectoryForCurrentUser
let dbPath = home.appendingPathComponent(
    "Library/Group Containers/group.com.apple.usernoted/db2/db").path

var db: OpaquePointer?
if sqlite3_open_v2(dbPath, &db, SQLITE_OPEN_READONLY, nil) != SQLITE_OK {
    elog("cannot open NC DB — grant Full Disk Access to ncread_helper: "
         + String(cString: sqlite3_errmsg(db)))
    exit(2)
}
elog("ncread: watching Notification Center DB")

// Cocoa reference epoch; start from "now" so we only emit fresh notifications.
var lastDelivered = Date().timeIntervalSinceReferenceDate
let query = """
    SELECT a.identifier, r.delivered_date, r.data
    FROM record r JOIN app a ON r.app_id = a.app_id
    WHERE r.delivered_date > ? ORDER BY r.delivered_date
    """

func emit(_ app: String, _ title: String, _ body: String) {
    let obj: [String: Any] = ["app": app, "title": title, "body": body]
    if let jd = try? JSONSerialization.data(withJSONObject: obj),
       var js = String(data: jd, encoding: .utf8) {
        js += "\n"
        FileHandle.standardOutput.write(js.data(using: .utf8)!)
    }
}

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
            emit(ident, title, body)
        }
    }
    sqlite3_finalize(stmt)
    Thread.sleep(forTimeInterval: 1.5)
}
