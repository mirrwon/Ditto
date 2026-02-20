import { useState } from "react";
import DiaryList from "../../components/diary/DiaryList";
import DiaryDetail from "../../components/diary/DiaryDetail";
import DiaryNewContainer from "../../components/diary/DiaryNewContainer";
import DiaryEditContainer from "../../components/diary/DiaryEditContainer";

const DiaryMainPage = () => {
    const [view, setView] = useState("LIST"); // LIST | DETAIL | NEW | EDIT
    const [selectedId, setSelectedId] = useState(null);

    const handleGoList = () => {
        setView("LIST");
        setSelectedId(null);
    };

    const handleViewDetail = (id) => {
        setSelectedId(id);
        setView("DETAIL");
    };

    const handleNewPost = () => {
        setView("NEW");
    };

    const handleEditPost = (id) => {
        setSelectedId(id);
        setView("EDIT");
    };

    const handleDeleteSuccess = () => {
        handleGoList();
    };

    const handleSaveSuccess = (id) => {
        if (id) {
            handleViewDetail(id);
        } else {
            handleGoList();
        }
    };

    return (
        <div className="diary-main-wrapper" style={{ height: '100%', overflowY: 'auto' }}>
            {view === "LIST" && (
                <DiaryList onViewDetail={handleViewDetail} onNewPost={handleNewPost} />
            )}
            {view === "DETAIL" && (
                <DiaryDetail
                    id={selectedId}
                    onGoList={handleGoList}
                    onEdit={handleEditPost}
                    onDeleteSuccess={handleDeleteSuccess}
                />
            )}
            {view === "NEW" && (
                <DiaryNewContainer
                    onSuccess={handleSaveSuccess}
                    onCancel={handleGoList}
                />
            )}
            {view === "EDIT" && (
                <DiaryEditContainer
                    id={selectedId}
                    onSuccess={handleSaveSuccess}
                    onCancel={() => handleViewDetail(selectedId)}
                />
            )}
        </div>
    );
};

export default DiaryMainPage;
